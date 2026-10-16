# Finance — 10-K filing diff with async-job pattern

End-to-end worked example: a financial-services partner submits two consecutive 10-K filing excerpts (this year vs. last year), the agent identifies material changes and risk flags, and returns a structured analyst-ready summary. Because filings are long and the analysis takes minutes, this uses LibraOS's async-job pattern — submit, poll, retrieve.

## What this demonstrates

- **Async jobs (`POST /agents/v1/{agent}/jobs`, then `GET …/jobs/{job_id}`)** — the partner submits the job, gets a `job_id` back immediately, polls until `status == "done"`, and reads the result from `result`. Called over HTTP for now: the SDK's `jobs` resource targets a route the server does not serve yet (libraos/libraos#1708). Avoids 30+ second HTTP timeouts on long analyses.
- **`search_web` for live enrichment** — `tools=["search_web"]` scopes the agent to web search alone, so it can look up the ticker, recent 8-K filings or peer context and cite each web source alongside the user-provided text. The search backend is a kernel setting (`TAVILY_API_KEY`, `BRAVE_API_KEY`, `SEARXNG_URL`, … or `LIBRA_OS_WEB_SEARCH`); on a kernel without one the tool returns no results and `web_citations` stays empty.
- **Structured output + a "material change" rubric** — the schema constrains the agent to a fixed taxonomy (revenue, leverage, segment-mix, going-concern, etc.) so downstream analyst tooling can pivot the result reliably. The schema is declared as `output_type`, which the chat endpoints validate, and repeated in the system prompt: a job's `result` is the reply as the model wrote it, so the script parses the JSON object out of it (`parse_json_reply`).

## Files

| File | Role |
|---|---|
| `sec_filing_diff.py` | Main partner-side script: submits the async job, polls, prints the structured diff |
| `sample_10k_2025.txt` | Synthetic FY2025 risk-factors excerpt |
| `sample_10k_2026.txt` | Synthetic FY2026 risk-factors excerpt with 3 material changes |

## Run

Tested against kernel v0.2.2 with `libraos-sdk` 2.0.0.

```bash
pip install libraos-sdk
export LIBRA_OS_URL=https://nova.your-company.example
export LIBRA_OS_API_KEY=msk_live_...
python sec_filing_diff.py
```

You'll see the script submit the job, poll status every 5 seconds (typically well under a minute; up to a few minutes with web search), and finally print:

```json
{
  "ticker": "ACME",
  "comparison_period": "FY2025 vs FY2026",
  "material_changes": [
    {
      "category": "leverage",
      "summary": "Long-term debt increased 38% YoY; new covenant added requiring..."
    },
    ...
  ],
  "overall_risk_delta": "elevated",
  "web_citations": [...]
}
```

A smoke check: `python sec_filing_diff.py | grep overall_risk_delta`.

## Adapting to your data

Replace the two sample text files with extracted Item 1A (Risk Factors) sections from your filing corpus. For larger jobs (full 10-K, multiple companies), upload the source text via `c.documents.upload` and reference the resulting document IDs in the job input — LibraOS will retrieve from its knowledge index instead of stuffing everything into the prompt.

For sector-specific work, swap the `material_changes.category` enum to match what your analysts actually pivot on (e.g., for banks: NIM, deposit-mix, CRE concentration; for SaaS: ARR, NRR, gross retention).
