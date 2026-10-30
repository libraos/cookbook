# Healthcare — clinical-note triage

End-to-end worked example: a healthcare partner sends a clinical-note text to a triage agent and gets back a structured triage decision (urgency level, suggested action, red flags).

## What this demonstrates

- **`output_type` JSON-schema validation** — the agent's reply is validated server-side against a contract before it leaves LibraOS. Partners' downstream code (EHR write-back, alerting, dashboards) gets a typed object every time, with no probabilistic free-text parsing. The validation runs on the agent chat endpoint, `POST /agents/v1/<agent>/chat`, which returns the parsed object as `output` — that is the call the script makes.
- **Per-patient memory (`X-Canonical-User`)** — every call carries the partner's internal patient identifier on the request. LibraOS keeps one observational-memory log per canonical user and agent, so this header gives each patient its own log and a triage decision for patient A never bleeds into patient B's session — a hard requirement for HIPAA-style minimum-necessary access. `X-End-User` is **not** enough: all end users of one service credential share a single log (verified on kernel v0.2.2 and v0.3.0). The header is honoured only for an admin-owned credential (an API key minted on v0.3.0 also needs `"allow_impersonation": true`) and is ignored silently otherwise; the id is prefixed so it cannot equal a real user's. See [before relying on it](../../docs/recipe-setup.md#shared-memory-in-the-local-kernel).
- **`brain=false` + `tool_scope="none"`** — one note in, one decision out on the skill tier; triage needs no tools, so the catalog stays out of the prompt.
- **Three violation modes for output validation** — `error` (reject + 422), `log` (return as-is + telemetry), `repair` (one bounded retry with the schema in the system prompt). The example uses `repair` because in clinical settings you'd rather a slightly slower second pass than a 422 the partner has to re-prompt.

## Files

| File | Role |
|---|---|
| `clinical_note_triage.py` | Main partner-side script: registers the agent, sends a synthetic note, prints the validated triage decision |
| `sample_note.txt` | Synthetic deidentified clinical note used as input |

## Run

Tested against kernel v0.3.0 with `libraos-sdk` 2.0.0.

```bash
pip install 'libraos-sdk>=2.0.0'
export LIBRA_OS_URL=https://nova.your-company.example
export LIBRA_OS_API_KEY=msk_live_...
python clinical_note_triage.py
```

You'll see LibraOS produce a structured JSON object like:

```json
{
  "patient_id": "PT-2026-0942",
  "urgency": "high",
  "suggested_action": "send_to_emergency",
  "red_flags": ["chest_pain_radiating", "diaphoresis", "history_of_cad"],
  "rationale": "..."
}
```

A smoke check: `python clinical_note_triage.py | grep '"urgency"'`.

## Adapting to your data

Replace `sample_note.txt` with a real (or representative) clinical-note format from your EHR. Extend the schema in `clinical_note_triage.py` to add fields your downstream systems require (ICD-10 codes, suggested specialty, minutes-to-action SLA, etc.). The `X-Canonical-User` value should be your stable internal patient identifier — never the patient's name or any other PHI element. Map it externally to the chart so the agent's memory is reproducible per patient without leaking PHI into LibraOS's logs.

## A note on data handling

This example sends synthetic clinical text through LibraOS. In a real deployment, the partner is responsible for ensuring the LLM provider LibraOS routes to (declared in `model_config`) is HIPAA-compliant for them — Anthropic, OpenAI, Google all offer BAA terms but require explicit enrollment. Verify with your compliance team before processing real PHI.
