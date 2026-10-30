"""Ticket routing — classify support tickets into a validated intent label.

End-to-end partner-side script:
    1. Creates a `ticket-router` skill agent whose reply is validated against a
       JSON-schema contract — every classification is a typed
       `{reasoning, intent}` object, never free-text your integration has to parse.
    2. Runs a small labelled validation set through it and reports accuracy —
       the loop you'd run before pointing live traffic at the classifier.
    3. `brain=false` skips the planner entirely: one ticket in, one verdict out,
       on the cheap skill tier. `tool_scope="none"`: no tools, no multi-step
       reasoning.

`output_type` is enforced on the agent chat endpoint, `POST
/agents/v1/{agent}/chat`: it validates the reply against the schema, runs the
`repair` retry, and returns the parsed object as `output`. That is the call the
loop below makes; `/v1/messages` returns the reply as the model wrote it.

The prose companion (decision criteria, taxonomy design, hierarchical
classification for large taxonomies, few-shot via a bound collection) lives in
the LibraOS docs: https://docs.meganova.ai → LibraOS → Use Cases → Ticket Routing.

Prerequisites::

    pip install libraos-sdk jsonschema
    export LIBRA_OS_URL=https://nova.your-company.example
    export LIBRA_OS_API_KEY=msk_live_...

Run::

    python ticket_routing.py
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
from pathlib import Path

import httpx
from jsonschema import validate

from libraos import Client
from libraos.errors import NotFoundError


# The contract every classification is validated against. `on_violation=repair`
# re-prompts the model once with the schema in the system prompt if its first
# reply doesn't conform — cheaper than a 422 your integration has to handle.
INTENT_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["reasoning", "intent"],
    "properties": {
        "reasoning": {
            "type": "string",
            "description": "One or two sentences: why this category fits the ticket.",
        },
        "intent": {
            "type": "string",
            "enum": [
                "Technical issue",
                "Account management",
                "Product information",
                "User guidance",
                "Feedback",
                "Order-related",
                "Security",
                "Emergency",
            ],
        },
    },
    "additionalProperties": False,
}

SAMPLE_PATH = Path(__file__).with_name("sample_tickets.jsonl")


def load_labelled() -> list[dict]:
    with SAMPLE_PATH.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


async def classify(http: httpx.AsyncClient, ticket: str) -> dict:
    """One ticket in, one validated verdict out.

    The agent chat endpoint validates the reply against INTENT_SCHEMA (and
    re-prompts once on a violation, per `on_violation=repair`); `output` is
    the parsed, schema-valid object. A reply that still violates the schema
    after the repair pass is a 422 `output_violation`.
    """
    # no_memory: each ticket is classified on its own. With memory on, the
    # verdicts on earlier tickets are recalled into this one and steer it.
    r = await http.post("/agents/v1/ticket-router/chat", json={"message": ticket, "no_memory": True})
    r.raise_for_status()
    verdict = r.json()["output"]
    validate(verdict, INTENT_SCHEMA)
    return verdict


async def main() -> dict:
    base_url = os.environ.get("LIBRA_OS_URL", "https://nova.your-company.example")
    api_key = os.environ["LIBRA_OS_API_KEY"]

    async with Client(base_url=base_url, api_key=api_key) as c:
        # Start clean: a run that failed part-way leaves this behind, and the
        # create call below would then fail with 409.
        with contextlib.suppress(NotFoundError):
            await c.agents.delete("ticket-router")

        # 1. The classifier. brain=false → straight to the model, no planner,
        #    on the kernel's skill-tier model. tool_scope="none" keeps the tool
        #    catalog out of the prompt: a classifier that can see shell and file
        #    tools is slower, costlier and occasionally tries to use them.
        await c.agents.create(
            id="ticket-router",
            type="skill",
            brain=False,
            tool_scope="none",
            output_type={"schema_inline": INTENT_SCHEMA, "on_violation": "repair"},
            system=(
                "You are a support-ticket classifier. Read the ticket and identify "
                "its primary intent. Always write your reasoning before choosing a "
                "category. If a ticket raises several issues, classify by the most "
                "urgent one and note the others in reasoning. Be concise. Reply "
                "with exactly one JSON object and nothing else, valid against "
                "this JSON Schema:\n" + json.dumps(INTENT_SCHEMA)
            ),
        )

        # 2. Validation loop — the gate you run before trusting live traffic.
        #    A `repair` retry doubles the latency of a verdict; give each call
        #    room.
        labelled = load_labelled()
        correct = 0
        async with httpx.AsyncClient(
            base_url=base_url, headers={"Authorization": f"Bearer {api_key}"}, timeout=180
        ) as http:
            for item in labelled:
                verdict = await classify(http, item["ticket"])
                got = verdict["intent"]
                ok = got == item["expected"]
                correct += ok
                mark = "✓" if ok else "✗"
                print(f"{mark} expected={item['expected']:<20} got={got:<20} :: {item['ticket'][:60]}")
                if not ok:
                    print(f"    reasoning: {verdict['reasoning']}")

        print(f"\nAccuracy: {correct}/{len(labelled)} = {correct / len(labelled):.0%}")
        print("Investigate every miss by reading its reasoning — misses cluster into "
              "wrong category description, ambiguous ticket, or a genuine edge case.")

        # 3. Cleanup for dev loops.
        await c.agents.delete("ticket-router")

        return {"correct": correct, "total": len(labelled)}


if __name__ == "__main__":
    asyncio.run(main())
