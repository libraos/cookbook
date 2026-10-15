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


async def main() -> None:
    base_url = os.environ.get("LIBRA_OS_URL", "https://nova.your-company.example")
    api_key = os.environ["LIBRA_OS_API_KEY"]

    async with Client(base_url=base_url, api_key=api_key) as c:
        # Start clean: a run that failed part-way leaves these behind, and the
        # create calls below would then fail with 409.
        for remove, name in ((c.agents.delete, "content-moderator"), (c.employees.delete, "trust-safety")):
            with contextlib.suppress(NotFoundError):
                await remove(name)

        await c.employees.create(
            id="trust-safety",
            display_name="Trust & Safety",
            model_config={
                "skill": {
                    "primary": "gemini/gemini-2.5-flash",
                    "fallback": ["anthropic/claude-haiku-4-5"],
                }
            },
        )

        await c.agents.create(
            id="content-moderator",
            type="skill",
            owner_employee="trust-safety",
            brain=False,
            description="Scores user-generated content against the platform policy.",
            output_type={"schema_inline": MODERATION_SCHEMA, "on_violation": "repair"},
            instructions=(
                "You are a content-moderation classifier applying the platform policy. "
                "Read the content, decide allow / flag / block, list every policy "
                "category it touches, and assign a 0-1 risk score. Be precise, not "
                "puritanical: allow benign content, flag genuinely ambiguous cases for "
                "human review, block only clear violations. Always give reasoning first."
            ),
        )

        labelled = load_labelled()
        correct = 0
        for item in labelled:
            resp = await c.messages.create(
                agent_id="content-moderator",
                messages=[{"role": "user", "content": item["content"]}],
                metadata={"agent_id": "content-moderator"},
            )
            v = json.loads(resp.text)
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
        await c.employees.delete("trust-safety")


if __name__ == "__main__":
    asyncio.run(main())
