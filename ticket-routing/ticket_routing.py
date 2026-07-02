"""Ticket routing — classify support tickets into a validated intent label.

End-to-end partner-side script:
    1. Creates a `ticket-router` skill agent whose reply is validated against a
       JSON-schema contract — every classification is a typed
       `{reasoning, intent}` object, never free-text your integration has to parse.
    2. Runs a small labelled validation set through it and reports accuracy —
       the loop you'd run before pointing live traffic at the classifier.
    3. `brain=false` skips the planner entirely: one ticket in, one verdict out,
       on the cheap skill tier. No tools, no multi-step reasoning.

The prose companion (decision criteria, taxonomy design, hierarchical
classification for large taxonomies, few-shot via a bound collection) lives in
the Nova OS docs: https://docs.meganova.ai → Nova OS → Use Cases → Ticket Routing.

Prerequisites::

    pip install nova-os-sdk
    export NOVA_OS_URL=https://nova.your-company.example
    export NOVA_OS_API_KEY=msk_live_...

Run::

    python ticket_routing.py
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from nova_os import Client


# The contract every classification is validated against. `violation_mode=repair`
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


async def main() -> None:
    base_url = os.environ.get("NOVA_OS_URL", "https://nova.your-company.example")
    api_key = os.environ["NOVA_OS_API_KEY"]

    async with Client(base_url=base_url, api_key=api_key) as c:
        # 1. Digital employee. Classification only needs the fast skill tier.
        await c.employees.create(
            id="support-desk",
            display_name="Support Desk",
            model_config={
                "skill": {
                    "primary": "gemini/gemini-2.5-flash",
                    "fallback": ["anthropic/claude-haiku-4-5"],
                }
            },
        )

        # 2. The classifier. brain=false → straight to the model, no planner.
        await c.agents.create(
            id="ticket-router",
            type="skill",
            owner_employee="support-desk",
            brain=False,
            description="Classifies a support ticket into a single primary intent label.",
            output_type={"schema": INTENT_SCHEMA, "violation_mode": "repair"},
            instructions=(
                "You are a support-ticket classifier. Read the ticket and identify "
                "its primary intent. Always write your reasoning before choosing a "
                "category. If a ticket raises several issues, classify by the most "
                "urgent one and note the others in reasoning. Be concise."
            ),
        )

        # 3. Validation loop — the gate you run before trusting live traffic.
        labelled = load_labelled()
        correct = 0
        for item in labelled:
            resp = await c.messages.create(
                agent_id="ticket-router",
                messages=[{"role": "user", "content": item["ticket"]}],
                metadata={"agent_id": "ticket-router"},
            )
            verdict = resp.structured_output if hasattr(resp, "structured_output") else resp
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

        # 4. Cleanup for dev loops.
        await c.agents.delete("ticket-router")
        await c.employees.delete("support-desk")


if __name__ == "__main__":
    asyncio.run(main())
