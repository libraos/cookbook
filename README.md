# LibraOS cookbook

Runnable examples for building on **LibraOS**, the agent runtime in
[`libraos/libraos`](https://github.com/libraos/libraos), called directly over
HTTP or through the [`libraos/sdk`](https://github.com/libraos/sdk) client.
Modeled on [`anthropics/claude-cookbooks`](https://github.com/anthropics/claude-cookbooks).

## What lives where

| Repo | Purpose |
|---|---|
| [`libraos/libraos`](https://github.com/libraos/libraos) | The kernel. Deploy this to host agents. |
| [`libraos/sdk`](https://github.com/libraos/sdk) | Client SDK plus per-resource call snippets (`messages.create`, `agents.list`, …): the minimal surface for calling a running kernel. |
| **this repo** | Examples that compose the kernel's APIs with the code around them. Pick by what you're building, not by API method. |

To learn the SDK surface ("how do I call `messages.create`?"), start in
[`libraos/sdk/examples`](https://github.com/libraos/sdk/tree/main/examples). To
build an application, start here.

## How this repo is organized

[Skills, agents, packs, missions and apps](docs/concepts.md): what each layer is and where it lives. Single-agent recipes are in [`recipes/`](recipes/), teams in [`packs/`](packs/), applications in [`apps/`](apps/).

## Get started

A local kernel in Docker, then the first things to build on it. Start here if
you're new. See [`get-started/`](get-started/README.md).

| Example | What it shows |
|---|---|
| [`get-started/01-first-agent/`](get-started/01-first-agent/) | Create an agent and talk to it, in bash or TypeScript |
| [`get-started/02-sign-in-with-libraos/`](get-started/02-sign-in-with-libraos/) | A browser app that signs people in with LibraOS (OIDC + PKCE, by hand) |

## Apps

Small but complete applications, each proven against a local kernel.

| App | What it shows |
|---|---|
| [`apps/digital-marketing-team/`](apps/digital-marketing-team/) | One mission to a Head of Marketing becomes a small department: a task graph, approval gates and one attributed report, followed live over a replayable event stream. Runs the [`marketing-team`](packs/marketing-team/) pack. |
| [`apps/personal-assistant/`](apps/personal-assistant/) | A signed-in user chats with an app's own agent, resumes past conversations, uploads documents it answers from, and is remembered across conversations. Vite + React + TypeScript. |

## Packs

Reusable teams: a director, specialist agents, knowledge, safety rules and the missions they deliver. See [`packs/`](packs/) and [concepts](docs/concepts.md).

| Pack | What it is |
|---|---|
| [`packs/marketing-team/`](packs/marketing-team/) | The digital marketing department: mission contract, example mission and knowledge |

## Recipes

Each recipe is the runnable companion to a Libra OS docs use-case guide (linked in its README) — prose there, working code here.

### Use-case recipes

| Recipe | What it shows |
|---|---|
| [`recipes/ticket-routing/`](recipes/ticket-routing/) | Classify support tickets into a validated `intent` with `output_type` + `repair`, plus an accuracy eval loop |
| [`recipes/content-moderation/`](recipes/content-moderation/) | Risk-score UGC (`allow`/`flag`/`block` + score) with `output_type`, layered on the built-in AI Firewall |
| [`recipes/document-qa/`](recipes/document-qa/) | Grounded, cited answers over ingested documents with `knowledge_bindings` + `knowledge_gate` (and honest refusal on a miss) |
| [`recipes/customer-support/`](recipes/customer-support/) | A persona that answers from a KB **and** calls a Mode B custom-tool webhook for live order status, with guardrails on |

### Vertical worked examples

| Recipe | What it shows |
|---|---|
| [`recipes/legaltech/`](recipes/legaltech/) | Contract clause extraction with structured output + a Mode B custom-tool webhook for partner-side precedent lookup |
| [`recipes/healthcare/`](recipes/healthcare/) | Clinical-note triage with `output_type` JSON-schema validation + per-end-user identity passthrough for HIPAA-style isolation |
| [`recipes/finance/`](recipes/finance/) | 10-K filing diff using the async-job pattern for long documents, with `web_search_config` for live market-data enrichment |

## Common prerequisites (recipes)

```bash
pip install nova-os-sdk
export NOVA_OS_URL=https://nova.your-company.example
export NOVA_OS_API_KEY=msk_live_...
```

Each recipe's `README.md` lists vertical-specific extras (FastAPI for the legaltech webhook, etc.).

## Sample data

All sample inputs are **synthetic**. The legaltech MSA, the healthcare clinical note, and the finance 10-K excerpts are constructed for documentation — they don't correspond to real contracts, real patients, or real filings. Replace them with your own data when adapting.

## Versioning

Recipes target the latest stable SDK release. If a recipe depends on a specific kernel build (e.g., a feature only available in `v0.1.7+`), its README will say so. The get-started examples and apps pin the kernel image in `get-started/docker-compose.yml`.
