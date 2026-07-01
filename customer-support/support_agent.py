"""Customer support — a context-aware agent that answers from a KB and takes actions.

End-to-end partner-side script:
    1. Ingests a small support knowledge base (policies, FAQs).
    2. Creates a persona agent that (a) answers product/policy questions from the
       bound KB with citations, and (b) calls a Mode B custom tool — an
       `order_lookup` webhook on your side — to fetch live order status.
    3. Asks one KB question (grounded answer) and one action question (tool call).

The default PII-redactor and AI-Firewall guardrails stay on — a support agent
handles customer text, so inbound abuse protection and outbound PII scrubbing
are exactly what you want. See the README for when to relax them.

Pair with `webhook_server.py` (FastAPI) running on `${NOVA_CB_URL}` so the
order-lookup tool callback has somewhere to land.

The prose companion (knowledge + tools + guardrails + streaming together) lives
in the Nova OS docs:
https://os.novaos.ai → Nova OS → Use Cases → Customer Support Agent.

Prerequisites::

    pip install nova-os-sdk
    export NOVA_OS_URL=https://nova.your-company.example
    export NOVA_OS_API_KEY=msk_live_...
    export NOVA_CB_URL=https://partner.example/nova/cb   # where webhook_server.py is reachable
    export NOVA_CB_SECRET=<your webhook secret>

Run::

    # terminal 1
    uvicorn webhook_server:app --port 8080
    # terminal 2
    python support_agent.py
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from nova_os import Client


COLLECTION = "support-kb"
KB_PATH = Path(__file__).with_name("sample_support_kb.md")

# Mode B custom tool: Nova OS POSTs a signed payload to callback_url when the
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
        "callback_url": os.environ.get("NOVA_CB_URL", "https://partner.example/nova/cb"),
    },
]


async def ask(c: Client, customer: str, question: str) -> None:
    resp = await c.messages.create(
        agent_id="support-agent",
        messages=[{"role": "user", "content": question}],
        metadata={"agent_id": "support-agent"},
        # Scope the agent's memory to this customer (their prior context never
        # bleeds into another customer's session).
        extra_headers={"X-End-User": customer},
    )
    text = resp.content if hasattr(resp, "content") else resp
    print(f"\n[{customer}] Q: {question}\nA: {text}")


async def main() -> None:
    base_url = os.environ.get("NOVA_OS_URL", "https://nova.your-company.example")
    api_key = os.environ["NOVA_OS_API_KEY"]

    async with Client(base_url=base_url, api_key=api_key) as c:
        # 1. Ingest the support KB (created on first ingest).
        await c.knowledge.ingest(
            content=KB_PATH.read_text(encoding="utf-8"),
            title="support-policies",
            collection=COLLECTION,
        )

        # 2. The support persona. brain=true so it can decide per turn between a
        #    KB answer and an order_lookup tool call. PII-redactor + firewall
        #    guardrails are on by default (not passed here).
        await c.employees.create(
            id="support-team",
            display_name="Support Team",
            model_config={
                "answer": {"primary": "anthropic/claude-opus-4-7", "fallback": ["gemini/gemini-2.5-pro"]},
                "skill": {"primary": "gemini/gemini-2.5-flash"},
            },
        )
        await c.agents.create(
            id="support-agent",
            type="persona",
            owner_employee="support-team",
            brain=True,
            knowledge_bindings=[COLLECTION],
            custom_tools=CUSTOM_TOOLS,
            description="Answers customer questions from the support KB and looks up live order status.",
            instructions=(
                "You are a friendly, accurate customer-support agent. Answer product and "
                "policy questions strictly from the retrieved knowledge base and cite the "
                "source. For questions about a specific order's status, call order_lookup "
                "with the order id and relay the result. If you don't know and it isn't in "
                "the KB, say so and offer to escalate — never invent a policy or a status."
            ),
        )

        # 3a. Knowledge question — answered from the bound KB.
        await ask(c, "cust-1042", "What's your refund window, and are digital downloads refundable?")

        # 3b. Action question — the agent calls the order_lookup webhook tool.
        await ask(c, "cust-1042", "Where is my order ORD-5591? It still hasn't arrived.")

        # 4. Cleanup for dev loops.
        await c.agents.delete("support-agent")
        await c.employees.delete("support-team")


if __name__ == "__main__":
    asyncio.run(main())
