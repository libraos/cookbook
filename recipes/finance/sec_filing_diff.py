"""Finance — 10-K filing year-over-year diff with async-job pattern.

End-to-end partner-side script:
    1. Creates a `filing-analyst` agent that may call `search_web` and whose
       reply follows a structured schema covering the analyst-ready material
       changes taxonomy.
    2. Submits an async job containing two 10-K Item 1A excerpts (FY2025 +
       FY2026). Returns immediately with a job_id.
    3. Polls job status every 5 seconds until complete.
    4. Prints the validated structured diff.

Async is the right fit because the analysis takes 60-180 seconds — well past
HTTP timeouts on most reverse proxies. The pattern generalises to any
long-running LibraOS workload (multi-document research, full-corpus risk
review, multi-step plan execution).

Prerequisites::

    pip install libraos-sdk
    export LIBRA_OS_URL=https://nova.your-company.example
    export LIBRA_OS_API_KEY=msk_live_...

Run::

    python sec_filing_diff.py
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


DIFF_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": [
        "ticker",
        "comparison_period",
        "material_changes",
        "overall_risk_delta",
    ],
    "properties": {
        "ticker": {"type": "string"},
        "comparison_period": {"type": "string"},
        "material_changes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["category", "summary", "direction"],
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": [
                            "revenue",
                            "leverage",
                            "liquidity",
                            "segment_mix",
                            "customer_concentration",
                            "regulatory",
                            "litigation",
                            "going_concern",
                            "auditor_change",
                            "other",
                        ],
                    },
                    "summary": {"type": "string"},
                    "direction": {
                        "type": "string",
                        "enum": ["risk_up", "risk_down", "neutral"],
                    },
                    "evidence_excerpt": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
        "overall_risk_delta": {
            "type": "string",
            "enum": ["materially_lower", "lower", "stable", "elevated", "materially_elevated"],
        },
        "web_citations": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["url", "snippet"],
                "properties": {
                    "url": {"type": "string", "format": "uri"},
                    "snippet": {"type": "string"},
                },
            },
        },
    },
    "additionalProperties": False,
}


SAMPLE_2025 = Path(__file__).with_name("sample_10k_2025.txt")
SAMPLE_2026 = Path(__file__).with_name("sample_10k_2026.txt")


def parse_json_reply(text: str) -> dict:
    """Parse the JSON object in a job result.

    `output_type` is validated on the synchronous chat endpoints; a job's
    `result` is the agent's reply as written, so tolerate a ```json fence or a
    sentence around the object.
    """
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError(f"no JSON object in job result: {text[:200]!r}")
    return json.loads(text[start : end + 1])


async def main() -> None:
    base_url = os.environ.get("LIBRA_OS_URL", "https://nova.your-company.example")
    api_key = os.environ["LIBRA_OS_API_KEY"]

    fy2025 = SAMPLE_2025.read_text(encoding="utf-8")
    fy2026 = SAMPLE_2026.read_text(encoding="utf-8")

    async with Client(base_url=base_url, api_key=api_key) as c:
        # Start clean: a run that failed part-way leaves this behind, and the
        # create call below would then fail with 409.
        with contextlib.suppress(NotFoundError):
            await c.agents.delete("filing-analyst")

        # 1. The analyst. `tools=["search_web"]` scopes it to web search alone
        #    (the backend — Tavily, Brave, SearXNG… — is a kernel setting, see
        #    README). The schema is declared as `output_type`, which the chat
        #    endpoints validate, and repeated in the system prompt because a
        #    job's `result` is the reply as the model wrote it.
        await c.agents.create(
            id="filing-analyst",
            type="skill",
            brain=False,
            tools=["search_web"],
            output_type={"schema_inline": DIFF_SCHEMA, "on_violation": "repair"},
            system=(
                "You are a filings analyst. Compare two 10-K Item 1A excerpts "
                "from the same issuer and identify every material change. Use "
                "search_web sparingly (at most a few calls) to look up the "
                "ticker, recent 8-K filings or peer context — every web source "
                "used must appear in web_citations with a verbatim snippet; if "
                "search is unavailable, leave web_citations empty. Do not invent "
                "figures. If a change is ambiguous, classify its direction as "
                "neutral and explain why. Reply with exactly one JSON object "
                "and nothing else, valid against this JSON Schema:\n"
                + json.dumps(DIFF_SCHEMA)
            ),
        )

        # 2. Kick off the async job: POST /agents/v1/{agent}/jobs. It is called
        #    directly here because the SDK's jobs resource targets a route the
        #    server does not serve yet (libraos/libraos#1708).
        payload = {
            "ticker": "ACME",
            "comparison_period": "FY2025 vs FY2026",
            "fy2025_item_1a": fy2025,
            "fy2026_item_1a": fy2026,
        }
        jobs_path = "/agents/v1/filing-analyst/jobs"
        async with httpx.AsyncClient(
            base_url=base_url, headers={"Authorization": f"Bearer {api_key}"}, timeout=60
        ) as http:
            r = await http.post(
                jobs_path,
                json={"message": json.dumps(payload)},
                # Re-submitting with the same key returns the same job.
                headers={"Idempotency-Key": "acme-fy26-diff-v1"},
            )
            r.raise_for_status()
            job_id = r.json()["job_id"]
            print(f"Submitted job: {job_id}")

            # 3. Poll until it finishes. Production code should cap polling at a
            #    sensible budget and surface progress to the UI (or follow
            #    GET {jobs_path}/{job_id}/stream instead of polling).
            for attempt in range(120):  # 120 * 5s = 10 min ceiling
                job = (await http.get(f"{jobs_path}/{job_id}")).json()
                print(f"  [{attempt:>2}] status={job['status']}")
                if job["status"] in ("done", "failed", "cancelled"):
                    break
                await asyncio.sleep(5)
            else:
                print("Polling budget exhausted — cancelling.")
                await http.delete(f"{jobs_path}/{job_id}")
                return

        if job["status"] != "done":
            print(f"Job did not complete cleanly: status={job['status']} error={job.get('error')!r}")
            return

        # 4. Print the diff.
        print()
        print("Material changes:")
        print(json.dumps(parse_json_reply(job["result"]), indent=2))

        # 5. Optional cleanup.
        await c.agents.delete("filing-analyst")


if __name__ == "__main__":
    asyncio.run(main())
