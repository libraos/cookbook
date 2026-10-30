"""Healthcare — clinical-note triage with structured output + per-patient isolation.

End-to-end partner-side script:
    1. Creates a `clinical-triage` agent whose reply is validated against a
       JSON-schema contract — partners receive a typed `{urgency, action, red_flags}`
       object every time, no free-text parsing.
    2. Sends a synthetic clinical note. The `X-Canonical-User` header carries
       the partner's stable internal patient identifier so the agent's
       observational memory is scoped per patient (HIPAA-style minimum-necessary
       isolation — patient A's conversation history never bleeds into B's).
       `X-End-User` alone does not do this: every end user of one service
       credential shares a single memory log per agent.
    3. Prints the validated triage decision.

`output_type` is enforced on the agent chat endpoint, `POST
/agents/v1/{agent}/chat`: it validates the reply against the schema, runs the
`repair` retry, and returns the parsed object as `output`. That is the call the
loop below makes; `/v1/messages` returns the reply as the model wrote it.

Prerequisites::

    pip install 'libraos-sdk>=2.0.0'
    export LIBRA_OS_URL=https://nova.your-company.example
    export LIBRA_OS_API_KEY=msk_live_...

Run::

    python clinical_note_triage.py
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


TRIAGE_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["patient_id", "urgency", "suggested_action", "red_flags", "rationale"],
    "properties": {
        "patient_id": {"type": "string"},
        "urgency": {
            "type": "string",
            "enum": ["low", "medium", "high", "critical"],
        },
        "suggested_action": {
            "type": "string",
            "enum": [
                "self_care_education",
                "schedule_pcp_followup",
                "schedule_urgent_followup",
                "send_to_urgent_care",
                "send_to_emergency",
                "telephone_advice_line",
            ],
        },
        "red_flags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Standardised flag tokens (e.g. chest_pain_radiating, diaphoresis)",
        },
        "rationale": {
            "type": "string",
            "description": "One-paragraph clinical rationale tying flags to action",
        },
        "icd10_suggested": {
            "type": "array",
            "items": {"type": "string", "pattern": "^[A-Z][0-9]{2}(\\.[0-9A-Z]{1,4})?$"},
            "description": "ICD-10 codes consistent with the note (advisory only)",
        },
    },
    "additionalProperties": False,
}


SAMPLE_NOTE_PATH = Path(__file__).with_name("sample_note.txt")


async def main() -> None:
    base_url = os.environ.get("LIBRA_OS_URL", "https://nova.your-company.example")
    api_key = os.environ["LIBRA_OS_API_KEY"]

    note_text = SAMPLE_NOTE_PATH.read_text(encoding="utf-8")

    # Stable per-patient identifier. NEVER use patient name or other PHI here —
    # map your internal chart ID externally and pass only the opaque token.
    patient_id = "PT-2026-0942"

    async with Client(base_url=base_url, api_key=api_key) as c:
        # Start clean: a run that failed part-way leaves this behind, and the
        # create call below would then fail with 409.
        with contextlib.suppress(NotFoundError):
            await c.agents.delete("clinical-triage")

        # 1. The triage agent. `output_type.on_violation=repair` means if the
        #    model's first reply doesn't match TRIAGE_SCHEMA, LibraOS re-prompts
        #    once with the schema in the system prompt before returning the
        #    result. Better than a 422 in a clinical workflow.
        #    brain=false: one note in, one decision out, on the kernel's
        #    skill-tier model. tool_scope="none": triage needs no tools.
        await c.agents.create(
            id="clinical-triage",
            type="skill",
            brain=False,
            tool_scope="none",
            output_type={"schema_inline": TRIAGE_SCHEMA, "on_violation": "repair"},
            system=(
                "You are a clinical triage decision-support tool. Read the note, "
                "identify red flags using standard clinical-decision keywords, and "
                "produce a triage decision. Be conservative — when in doubt, escalate. "
                "Never fabricate findings not in the note. The patient_id field MUST "
                "match the Patient ID given in the request. Reply with exactly one "
                "JSON object and nothing else, valid against this JSON Schema:\n"
                + json.dumps(TRIAGE_SCHEMA)
            ),
        )

        # 2. Send the note to the agent chat endpoint, which validates the
        #    reply against TRIAGE_SCHEMA (re-prompting once on a violation)
        #    and returns the parsed object as `output`. The patient identifier
        #    flows on the request as X-Canonical-User so the agent's
        #    observational memory is scoped per patient — A's prior visits never
        #    bleed into B's reasoning. The header is honoured only for an
        #    admin-owned credential (an API key minted on v0.3.0 also needs allow_impersonation).
        #    A clinical note is a long prompt and `repair` may add a second
        #    pass: give the call room.
        async with httpx.AsyncClient(
            base_url=base_url, headers={"Authorization": f"Bearer {api_key}"}, timeout=300
        ) as http:
            r = await http.post(
                "/agents/v1/clinical-triage/chat",
                json={
                    "message": (
                        f"Patient ID: {patient_id}\n\n"
                        f"Clinical note (deidentified):\n\n{note_text}\n\n"
                        f"Produce a triage decision."
                    )
                },
                # Prefixed so a patient id can never equal a real user's id
                # (canonical ids share one namespace with signed-in users).
                headers={"X-Canonical-User": f"patient:{patient_id}"},
            )
            r.raise_for_status()  # 422 output_violation if repair also fails

        # 3. Validated structured output — `output` is already the parsed object.
        decision = r.json()["output"]
        print("Triage decision:")
        print(json.dumps(decision, indent=2))

        # 4. Optional cleanup for dev loops.
        await c.agents.delete("clinical-triage")


if __name__ == "__main__":
    asyncio.run(main())
