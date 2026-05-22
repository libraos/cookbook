# nova-os-cookbook

End-to-end recipes for building partner applications on top of **Nova OS** — the agent runtime served by [`MeganovaAI/nova-os`](https://github.com/MeganovaAI/nova-os) and consumed via the [`nova-os-sdk`](https://github.com/MeganovaAI/nova-os-sdk).

Each recipe is a runnable, self-contained workflow that wires the SDK together with surrounding partner-side code: webhook receivers, sample input documents, structured-output validators, identity passthrough, async-job patterns. Modeled on [`anthropics/claude-cookbooks`](https://github.com/anthropics/claude-cookbooks).

## What lives where

| Repo | Purpose |
|---|---|
| [`MeganovaAI/nova-os`](https://github.com/MeganovaAI/nova-os) | Server runtime. Deploy this to host agents. |
| [`MeganovaAI/nova-os-sdk`](https://github.com/MeganovaAI/nova-os-sdk) | Client SDK + per-resource call-pattern snippets (`messages.create`, `agents.list`, …). The minimal surface a partner needs to call a running Nova OS. |
| **this repo** | Vertical workflow recipes that compose the SDK with surrounding partner code. Pick by use case, not by API method. |

If you're trying to learn the SDK surface ("how do I call `messages.create`?"), start in `nova-os-sdk/examples/`. If you're building an application ("how do I extract clauses from contracts?"), start here.

## Recipes

| Vertical | What it shows |
|---|---|
| [`legaltech/`](legaltech/) | Contract clause extraction with structured output + a Mode B custom-tool webhook for partner-side precedent lookup |
| [`healthcare/`](healthcare/) | Clinical-note triage with `output_type` JSON-schema validation + per-end-user identity passthrough for HIPAA-style isolation |
| [`finance/`](finance/) | 10-K filing diff using the async-job pattern for long documents, with `web_search_config` for live market-data enrichment |

## Common prerequisites

```bash
pip install nova-os-sdk
export NOVA_OS_URL=https://nova.your-company.example
export NOVA_OS_API_KEY=msk_live_...
```

Each recipe's `README.md` lists vertical-specific extras (FastAPI for the legaltech webhook, etc.).

## Sample data

All sample inputs are **synthetic**. The legaltech MSA, the healthcare clinical note, and the finance 10-K excerpts are constructed for documentation — they don't correspond to real contracts, real patients, or real filings. Replace them with your own data when adapting.

## Versioning

Recipes target the latest stable `nova-os-sdk` release. If a recipe depends on a specific server build (e.g., a feature only available in `nova-os:v0.1.7+`), its README will say so.
