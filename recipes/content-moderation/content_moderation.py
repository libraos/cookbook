"""Content moderation — risk-score user-generated content against your policy.

End-to-end partner-side script:
    1. Creates a `content-moderator` skill agent whose reply is validated against
       a JSON-schema contract — every decision is a typed
       `{reasoning, verdict, categories, risk_score}` object.
    2. Runs a small labelled set of UGC snippets through it and reports accuracy.
    3. Layers on top of LibraOS's built-in AI Firewall: the firewall is a
       platform-level inbound guardrail (prompt-injection / jailbreak / abuse)
       that runs BEFORE your agent; this agent is your *domain* policy on top —
       the two are complementary, not a substitute for each other.

`output_type` is enforced on the agent chat endpoint, `POST
/agents/v1/{agent}/chat`: it validates the reply against the schema, runs the
`repair` retry, and returns the parsed object as `output`. That is the call the
loop below makes; `/v1/messages` returns the reply as the model wrote it.

The prose companion (policy design, category taxonomy, the firewall threshold
knob) lives in the LibraOS docs:
https://docs.meganova.ai → LibraOS → Use Cases → Content Moderation.

Prerequisites::

    pip install libraos-sdk
    export LIBRA_OS_URL=https://nova.your-company.example
    export LIBRA_OS_API_KEY=msk_live_...

Run::

    python content_moderation.py
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
from pathlib import Path

import httpx

from libraos import Client
from libraos.errors import NotFoundError


MODERATION_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["reasoning", "verdict", "categories", "risk_score"],
    "properties": {
        "reasoning": {
            "type": "string",
            "description": "Brief explanation tying the content to the policy decision.",
        },
        "verdict": {
            "type": "string",
            "enum": ["allow", "flag", "block"],
            "description": "allow = publish; flag = queue for human review; block = reject.",
        },
        "categories": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": [
                    "harassment",
                    "hate",
                    "sexual",
                    "violence",
                    "self_harm",
                    "spam",
                    "pii",
                    "none",
                ],
            },
            "description": "Every policy category the content touches (or ['none']).",
        },
        "risk_score": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
            "description": "0 = clearly benign, 1 = clearly violating.",
        },
    },
    "additionalProperties": False,
}

SAMPLE_PATH = Path(__file__).with_name("sample_content.jsonl")


def load_labelled() -> list[dict]:
    with SAMPLE_PATH.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


async def moderate(http: httpx.AsyncClient, content: str) -> dict:
    """One snippet in, one validated decision out.

    The agent chat endpoint validates the reply against MODERATION_SCHEMA
    (and re-prompts once on a violation, per `on_violation=repair`); `output`
    is the parsed, schema-valid object. A reply that still violates the
    schema after the repair pass is a 422 `output_violation`.
    """
    # no_memory: each item is judged on its own. With memory on, verdicts on
    # earlier items are recalled into this one and steer it.
    r = await http.post("/agents/v1/content-moderator/chat", json={"message": content, "no_memory": True})
    r.raise_for_status()
    return r.json()["output"]


async def main() -> None:
    base_url = os.environ.get("LIBRA_OS_URL", "https://nova.your-company.example")
    api_key = os.environ["LIBRA_OS_API_KEY"]

    async with Client(base_url=base_url, api_key=api_key) as c:
        # Start clean: a run that failed part-way leaves this behind, and the
        # create call below would then fail with 409.
        with contextlib.suppress(NotFoundError):
            await c.agents.delete("content-moderator")

        # brain=false: one call per item on the kernel's skill-tier model.
        # tool_scope="none": a classifier needs no tools, and leaving the
        # catalog in the prompt makes it slower and occasionally tool-happy.
        await c.agents.create(
            id="content-moderator",
            type="skill",
            brain=False,
            tool_scope="none",
            output_type={"schema_inline": MODERATION_SCHEMA, "on_violation": "repair"},
            system=(
                "You are a content-moderation classifier applying the platform policy. "
                "Read the content, decide allow / flag / block, list every policy "
                "category it touches, and assign a 0-1 risk score. Be precise, not "
                "puritanical: allow benign content, flag genuinely ambiguous cases for "
                "human review, block only clear violations. Always give reasoning first. "
                "Reply with exactly one JSON object and nothing else, valid against "
                "this JSON Schema:\n" + json.dumps(MODERATION_SCHEMA)
            ),
        )

        # A `repair` retry doubles the latency of a decision; give each call room.
        labelled = load_labelled()
        correct = 0
        async with httpx.AsyncClient(
            base_url=base_url, headers={"Authorization": f"Bearer {api_key}"}, timeout=180
        ) as http:
            for item in labelled:
                v = await moderate(http, item["content"])
                ok = v["verdict"] == item["expected"]
                correct += ok
                mark = "✓" if ok else "✗"
                print(
                    f"{mark} expected={item['expected']:<5} got={v['verdict']:<5} "
                    f"risk={v['risk_score']:.2f} cats={','.join(v['categories'])} "
                    f":: {item['content'][:50]}"
                )
                if not ok:
                    print(f"    reasoning: {v['reasoning']}")

        print(f"\nVerdict accuracy: {correct}/{len(labelled)} = {correct / len(labelled):.0%}")
        print("Tune your thresholds on risk_score: e.g. auto-block ≥ 0.85, human-review "
              "0.4–0.85, auto-allow < 0.4 — calibrate the bands to your appetite.")

        await c.agents.delete("content-moderator")


if __name__ == "__main__":
    asyncio.run(main())
