"""Legaltech — contract clause extraction with custom-tool callback.

End-to-end partner-side script:
    1. Imports an employee bundle that defines a `contracts-reviewer` employee
       and its `legal-clause-extractor` agent: a structured-output contract
       and a Mode B custom tool the agent can call to look up precedent in
       the partner's own clause DB.
    2. Submits an MSA text. LibraOS routes it through the agent, which
       extracts clauses, calls back to the precedent-lookup tool one or
       more times, and returns a structured JSON object.
    3. Pretty-prints the validated structured output.

`output_type` is enforced on the agent chat endpoint, `POST
/agents/v1/{agent}/chat`: it validates the reply against the schema, runs the
`repair` retry, and returns the parsed object as `output`. That is the call
step 2 makes; `/v1/messages` returns the reply as the model wrote it.

Custom tools live in the agent definition file (`custom_tools:` frontmatter),
which is why the agent is created from a bundle rather than with
`c.agents.create(...)`: the bundle import is the API that takes an agent file.

Pair with `webhook_server.py` (FastAPI) running on `${LIBRA_OS_CB_URL}` so the
precedent-lookup tool callback has somewhere to land. The LibraOS host signs
every callback with the secret held in the environment variable named by
`LIBRA_OS_CB_SECRET_REF` (default `LIBRA_OS_CALLBACK_SECRET_LEGAL`); the
webhook server verifies with the same value, passed as `LIBRA_OS_CB_SECRET`.

Prerequisites::

    pip install libraos-sdk
    export LIBRA_OS_URL=https://nova.your-company.example
    export LIBRA_OS_API_KEY=msk_live_...
    export LIBRA_OS_CB_URL=https://partner.example/nova/cb/
    export LIBRA_OS_CB_SECRET=<your webhook secret>

Run::

    python contract_clause_extraction.py
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


EMPLOYEE_ID = "contracts-reviewer"
AGENT_ID = "legal-clause-extractor"

# Name of the environment variable on the LibraOS host that holds the webhook
# secret. The kernel only signs with variables in its LIBRA_OS_CALLBACK_SECRET_*
# namespace (or an explicit LIBRA_OS_CALLBACK_SECRET_REFS allowlist).
CB_SECRET_REF = os.environ.get("LIBRA_OS_CB_SECRET_REF", "LIBRA_OS_CALLBACK_SECRET_LEGAL")

CLAUSE_OUTPUT_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["contract_id", "clauses"],
    "properties": {
        "contract_id": {"type": "string"},
        "clauses": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["type", "text", "risk_flag"],
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": [
                            "limitation_of_liability",
                            "indemnification",
                            "termination",
                            "ip_assignment",
                            "confidentiality",
                            "payment_terms",
                            "warranty",
                            "force_majeure",
                            "other",
                        ],
                    },
                    "text": {"type": "string", "description": "Verbatim clause excerpt"},
                    "risk_flag": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                    },
                    "rationale": {"type": "string"},
                    "precedent_score": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                        "description": "From the partner-side lookup_clause_precedent callback",
                    },
                },
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}


CUSTOM_TOOLS: list[dict] = [
    {
        "name": "lookup_clause_precedent",
        "description": (
            "Query the partner's clause-precedent database for a similarity score "
            "and one example precedent text. Use this when you have extracted a "
            "clause and want to score how unusual its phrasing is."
        ),
        "input_schema": {
            "type": "object",
            "required": ["clause_text", "clause_type"],
            "properties": {
                "clause_text": {"type": "string"},
                "clause_type": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "callback": {
            "url": os.environ.get("LIBRA_OS_CB_URL", "https://partner.example/nova/cb/"),
            "auth": {"type": "hmac_sha256", "secret_ref": CB_SECRET_REF},
        },
    },
]

SYSTEM_PROMPT = (
    "You are a contract-review assistant. Extract every operative clause from "
    "the agreement you are given. For each clause call lookup_clause_precedent "
    "with the verbatim text and your inferred clause_type, then record the "
    "returned score as precedent_score. Flag a clause materially out of line "
    "with the precedent corpus (below_threshold true) as risk_flag high. Reply "
    "with exactly one JSON object and nothing else, valid against this JSON "
    "Schema:\n" + json.dumps(CLAUSE_OUTPUT_SCHEMA)
)

SAMPLE_MSA_PATH = Path(__file__).with_name("sample_msa.txt")


def frontmatter(fields: dict) -> str:
    """Render agent/employee frontmatter. JSON is valid YAML, so one
    `key: <json>` line per field keeps the file both exact and readable."""
    return "---\n" + "".join(f"{k}: {json.dumps(v)}\n" for k, v in fields.items()) + "---\n"


def employee_bundle() -> bytes:
    """The zip `POST /v1/managed/employees/bundle/import` takes — the same
    layout `GET /v1/managed/employees/{id}/bundle/export` produces."""
    employee = {"id": EMPLOYEE_ID, "display_name": "Contracts Reviewer"}
    agent = {
        "name": AGENT_ID,
        "agent_type": "skill",
        "owner_employee": EMPLOYEE_ID,
        # Structured output + custom-tool wiring are agent-level — every chat
        # hits the same contract. tool_scope "none" keeps the catalog out;
        # custom_tools stay.
        "brain": False,
        "tool_scope": "none",
        "output_type": {"schema_inline": CLAUSE_OUTPUT_SCHEMA, "on_violation": "repair"},
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


async def main() -> None:
    base_url = os.environ.get("LIBRA_OS_URL", "https://nova.your-company.example")
    api_key = os.environ["LIBRA_OS_API_KEY"]

    msa_text = SAMPLE_MSA_PATH.read_text(encoding="utf-8")

    async with Client(base_url=base_url, api_key=api_key) as c:
        # 1. Start clean: an agent of the same name created with
        #    `c.agents.create(...)` would shadow the bundle's definition.
        with contextlib.suppress(NotFoundError):
            await c.agents.delete(AGENT_ID)

        # 2. Import the employee + agent. on_conflict=overwrite makes re-runs
        #    (and runs after a failed run) idempotent.
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

        # 3. Send the MSA to the agent chat endpoint. The agent calls
        #    lookup_clause_precedent zero or more times via the Mode B webhook
        #    before producing its final reply, which the endpoint validates
        #    against CLAUSE_OUTPUT_SCHEMA (re-prompting once on a violation).
        #    One webhook round-trip per clause: give the call minutes.
        async with httpx.AsyncClient(
            base_url=base_url, headers={"Authorization": f"Bearer {api_key}"}, timeout=600
        ) as http:
            r = await http.post(
                f"/agents/v1/{AGENT_ID}/chat",
                json={
                    "message": (
                        f"Contract ID: MSA-2026-042\n\n"
                        f"Extract every operative clause from the agreement below. "
                        f"For each one, call lookup_clause_precedent with the verbatim "
                        f"text + your inferred clause_type, then attach the precedent_score "
                        f"to the result. Flag any clause materially out of line with the "
                        f"precedent corpus as risk_flag=high.\n\n"
                        f"---\n{msa_text}\n---"
                    )
                },
            )
            r.raise_for_status()  # 422 output_violation if repair also fails

        # 4. `output` is the parsed, schema-valid object — no free text to
        #    re-parse.
        structured = r.json()["output"]
        print("Extracted clauses:")
        print(json.dumps(structured, indent=2))

        # 5. (Optional in prod, shown for clean dev loops.)
        for remove, name in ((c.agents.delete, AGENT_ID), (c.employees.delete, EMPLOYEE_ID)):
            with contextlib.suppress(NotFoundError):
                await remove(name)


if __name__ == "__main__":
    asyncio.run(main())
