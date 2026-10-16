"""Customer support — a context-aware agent that answers from a KB and takes actions.

End-to-end partner-side script:
    1. Ingests a small support knowledge base (policies, FAQs).
    2. Imports an employee bundle that defines the support agent: it answers
       product/policy questions from the bound KB with citations, and calls a
       Mode B custom tool — an `order_lookup` webhook on your side — to fetch
       live order status.
    3. Asks one KB question (grounded answer) and one action question (tool call).

Custom tools live in the agent definition file (`custom_tools:` frontmatter),
which is why the agent is created from a bundle rather than with
`c.agents.create(...)`: the bundle import is the API that takes an agent file.

The default PII-redactor and AI-Firewall guardrails stay on — a support agent
handles customer text, so inbound abuse protection and outbound PII scrubbing
are exactly what you want. See the README for when to relax them.

Pair with `webhook_server.py` (FastAPI) running on `${LIBRA_OS_CB_URL}` so the
order-lookup tool callback has somewhere to land. The LibraOS host signs every
callback with the secret held in the environment variable named by
`LIBRA_OS_CB_SECRET_REF` (default `LIBRA_OS_CALLBACK_SECRET_SUPPORT`); the
webhook server verifies with the same value, passed as `LIBRA_OS_CB_SECRET`.

The prose companion (knowledge + tools + guardrails + streaming together) lives
in the LibraOS docs:
https://docs.meganova.ai → LibraOS → Use Cases → Customer Support Agent.

Prerequisites::

    pip install 'libraos-sdk>=2.0.0'
    export LIBRA_OS_URL=https://nova.your-company.example
    export LIBRA_OS_API_KEY=msk_live_...
    export LIBRA_OS_CB_URL=https://partner.example/nova/cb/   # where webhook_server.py is reachable
    export LIBRA_OS_CB_SECRET=<your webhook secret>

Run::

    # terminal 1
    uvicorn webhook_server:app --port 8080
    # terminal 2
    python support_agent.py
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import os
import zipfile
from pathlib import Path

import httpx

from libraos import Client
from libraos.errors import NotFoundError


COLLECTION = "support-kb"
KB_PATH = Path(__file__).with_name("sample_support_kb.md")

EMPLOYEE_ID = "support-team"
AGENT_ID = "support-agent"

# Name of the environment variable on the LibraOS host that holds the webhook
# secret. The kernel only signs with variables in its LIBRA_OS_CALLBACK_SECRET_*
# namespace (or an explicit LIBRA_OS_CALLBACK_SECRET_REFS allowlist).
CB_SECRET_REF = os.environ.get("LIBRA_OS_CB_SECRET_REF", "LIBRA_OS_CALLBACK_SECRET_SUPPORT")

# Mode B custom tool: LibraOS POSTs a signed payload to callback.url when the
# agent decides to look up an order. The partner-side handler lives in
# webhook_server.py.
CUSTOM_TOOLS: list[dict] = [
    {
        "name": "order_lookup",
        "description": (
            "Look up the current status of a customer's order by order id. Use this "
            "whenever the customer asks about the state, shipping, or delivery of a "
            "specific order."
        ),
        "input_schema": {
            "type": "object",
            "required": ["order_id"],
            "properties": {"order_id": {"type": "string"}},
            "additionalProperties": False,
        },
        "callback": {
            "url": os.environ.get("LIBRA_OS_CB_URL", "https://partner.example/nova/cb/"),
            "auth": {"type": "hmac_sha256", "secret_ref": CB_SECRET_REF},
        },
    },
]

SYSTEM_PROMPT = (
    "You are a friendly, accurate customer-support agent. Answer product and "
    "policy questions strictly from the retrieved knowledge base and cite the "
    "source. For questions about a specific order's status, call order_lookup "
    "with the order id and relay the result. If you don't know and it isn't in "
    "the KB, say so and offer to escalate — never invent a policy or a status."
)


def frontmatter(fields: dict) -> str:
    """Render agent/employee frontmatter. JSON is valid YAML, so one
    `key: <json>` line per field keeps the file both exact and readable."""
    return "---\n" + "".join(f"{k}: {json.dumps(v)}\n" for k, v in fields.items()) + "---\n"


def employee_bundle() -> bytes:
    """The zip `POST /v1/managed/employees/bundle/import` takes — the same
    layout `GET /v1/managed/employees/{id}/bundle/export` produces."""
    employee = {"id": EMPLOYEE_ID, "display_name": "Support Team"}
    agent = {
        "name": AGENT_ID,
        "agent_type": "skill",
        "owner_employee": EMPLOYEE_ID,
        # One call per turn: answer from the injected KB passages or call the
        # tool. tool_scope "none" keeps the catalog out; custom_tools stay.
        "brain": False,
        "tool_scope": "none",
        "knowledge_bindings": [COLLECTION],
        "custom_tools": CUSTOM_TOOLS,
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "manifest.json",
            json.dumps({"schema_version": 1, "employee_id": EMPLOYEE_ID, "agents": [AGENT_ID]}),
        )
        z.writestr("employee.md", frontmatter(employee))
        z.writestr(f"agents/{AGENT_ID}.md", frontmatter(agent) + "\n" + SYSTEM_PROMPT + "\n")
    return buf.getvalue()


async def reload_agents(c: Client) -> None:
    """Make the kernel load the bundle's agent file.

    Kernel v0.2.2 registers the bundle's employee at once but reads its agent
    file on the next agent-registry reload, which any write to `/v1/agents`
    (or a SIGHUP to the kernel) triggers. A throwaway agent write is that
    nudge.
    """
    await c.agents.create(id=f"{AGENT_ID}-reload", type="skill", tool_scope="none", system="reload")
    await c.agents.delete(f"{AGENT_ID}-reload")


async def ask(c: Client, customer: str, question: str) -> None:
    resp = await c.messages.create(
        agent_id=AGENT_ID,
        messages=[{"role": "user", "content": question}],
        # Sent as X-End-User: memory is kept per customer, so one customer's
        # context never reaches another's session.
        end_user=customer,
    )
    text = resp.text
    print(f"\n[{customer}] Q: {question}\nA: {text}")


async def main() -> None:
    base_url = os.environ.get("LIBRA_OS_URL", "https://nova.your-company.example")
    api_key = os.environ["LIBRA_OS_API_KEY"]

    # A turn that calls the webhook is two model calls plus your handler.
    async with Client(base_url=base_url, api_key=api_key, timeout=180) as c:
        # 1. Ingest the support KB (created on first ingest).
        await c.knowledge.ingest(
            content=KB_PATH.read_text(encoding="utf-8"),
            title="support-policies",
            collection=COLLECTION,
        )

        # 2. Start clean: an agent of the same name created with
        #    `c.agents.create(...)` would shadow the bundle's definition.
        with contextlib.suppress(NotFoundError):
            await c.agents.delete(AGENT_ID)

        # 3. Import the employee + agent. on_conflict=overwrite makes re-runs
        #    (and runs after a failed run) idempotent. PII-redactor + firewall
        #    guardrails are on by default (not declared here).
        async with httpx.AsyncClient(
            base_url=base_url, headers={"Authorization": f"Bearer {api_key}"}, timeout=60
        ) as http:
            r = await http.post(
                "/v1/managed/employees/bundle/import",
                params={"on_conflict": "overwrite"},
                content=employee_bundle(),
                headers={"Content-Type": "application/zip"},
            )
            r.raise_for_status()
            print(f"Imported bundle: {r.json()}")
        await reload_agents(c)

        # 4a. Knowledge question — answered from the bound KB.
        await ask(c, "cust-1042", "What's your refund window, and are digital downloads refundable?")

        # 4b. Action question — the agent calls the order_lookup webhook tool.
        await ask(c, "cust-1042", "Where is my order ORD-5591? It still hasn't arrived.")

        # 5. Cleanup for dev loops.
        for remove, name in ((c.agents.delete, AGENT_ID), (c.employees.delete, EMPLOYEE_ID)):
            with contextlib.suppress(NotFoundError):
                await remove(name)


if __name__ == "__main__":
    asyncio.run(main())
