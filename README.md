# LibraOS cookbook

Runnable examples for building on **LibraOS**, the agent runtime distributed by
[`libraos/runtime`](https://github.com/libraos/runtime), called directly over
HTTP or through the [`libraos/sdk`](https://github.com/libraos/sdk) client.
Modeled on [`anthropics/claude-cookbooks`](https://github.com/anthropics/claude-cookbooks).

## What lives where

| Repo | Purpose |
|---|---|
| [`libraos/runtime`](https://github.com/libraos/runtime) | Public kernel binaries and release checksums. |
| [`libraos/stack`](https://github.com/libraos/stack) | Reference deployment manifests. For a local cookbook setup, use [Get started](get-started/). |
| [`libraos/sdk`](https://github.com/libraos/sdk) | Client SDK plus per-resource call snippets (`messages.create`, `agents.list`, …): the minimal surface for calling a running kernel. |
| **this repo** | Examples that compose the kernel's APIs with the code around them. Pick by what you're building, not by API method. |

To learn the SDK surface ("how do I call `messages.create`?"), start in
[`libraos/sdk/python/examples`](https://github.com/libraos/sdk/tree/main/python/examples). To
build an application, start here.

## Choose your starting point

| Entry | Start here |
|---|---|
| **Learn Step by Step** | [Learning paths](docs/learning-paths.md): First Agent → structured output → choose Knowledge, Tools or Memory → a combined workflow → complete apps |
| **Explore by Capability** | [Knowledge](recipes/document-qa/), [Tools](recipes/tool-calling/), [Memory & user isolation](recipes/memory-isolation/), [Async jobs & recovery](recipes/async-jobs/), [approval mechanisms](docs/approval-mechanisms.md) |
| **See Complete Applications** | [Personal Assistant](apps/personal-assistant/) or [Marketing Team](apps/digital-marketing-team/) with its [Mission Console](apps/mission-console/). [Existing App Integration](docs/learning-paths.md#see-complete-applications) is not available as a runnable tutorial. |

Knowledge, Tools and Memory are **independent L2 branches**. Choose the one
you need; completing all three is not an entry requirement. Browser sign-in is
an application-integration branch, not the second mandatory Agent lesson.

Every core example names an observable success and a failure/boundary check.
[Validation](docs/validation.md) distinguishes offline protocol tests from
opt-in Runtime/model evaluations and records what has actually been verified.
For a shared Python environment and a local token, see [recipe setup](docs/recipe-setup.md).

## How this repo is organized

[Skills, agents, packs, missions and apps](docs/concepts.md): what each layer is and where it lives. Single-agent recipes are in [`recipes/`](recipes/), teams in [`packs/`](packs/), applications in [`apps/`](apps/), and code shared between apps in [`shared/`](shared/).

## Get started

A local kernel in Docker, then the first things to build on it. Start here if
you're new. See [`get-started/`](get-started/README.md).

| Example | What it shows |
|---|---|
| [`get-started/01-first-agent/`](get-started/01-first-agent/) | Create an agent and talk to it, in Bash, Python or TypeScript |
| [`get-started/02-sign-in-with-libraos/`](get-started/02-sign-in-with-libraos/) | A browser app that signs people in with LibraOS (OIDC + PKCE, by hand) |

## Apps

Small but complete applications, each verified on kernel v0.3.0 as recorded in [Validation](docs/validation.md).

| App | What it shows |
|---|---|
| [`apps/digital-marketing-team/`](apps/digital-marketing-team/) | One mission to a Head of Marketing becomes a small department: a task graph, approval gates and one attributed report, followed live over a replayable event stream. Runs the [`marketing-team`](packs/marketing-team/) pack. |
| [`apps/mission-console/`](apps/mission-console/) | A reusable client for the marketing mission: follow the team and plan, answer decisions, read the report. Today its catalog has one runnable mission. Built on the shared [mission client](shared/mission-client/). |
| [`apps/personal-assistant/`](apps/personal-assistant/) | A signed-in user chats with an app's own agent, resumes past conversations, uploads documents it answers from, and is remembered across conversations. Vite + React + TypeScript. |

## Packs

Reusable teams: a director, specialist agents, knowledge, safety rules and the missions they deliver. See [`packs/`](packs/) and [concepts](docs/concepts.md).

| Pack | What it is |
|---|---|
| [`packs/marketing-team/`](packs/marketing-team/) | The digital marketing department: mission contract, example mission and knowledge |

## Recipes

Each recipe includes its setup and observable result. See also the public
[LibraOS cookbook guide](https://libraos.com/docs/cookbook/).

### Use-case recipes

| Recipe | What it shows |
|---|---|
| [`recipes/ticket-routing/`](recipes/ticket-routing/) | Classify support tickets into a validated `intent` with `output_type` + `repair`, plus an accuracy eval loop |
| [`recipes/tool-calling/`](recipes/tool-calling/) | **L2 Tools:** signed read-only order lookup, missing orders, callback receipts and unavailable-service checks |
| [`recipes/memory-isolation/`](recipes/memory-isolation/) | **L2 Memory:** fresh-conversation recall with two ordinary authenticated users and an identity-override boundary check |
| [`recipes/async-jobs/`](recipes/async-jobs/) | **L3 Async:** native HTTP submission, saved recovery receipt, bounded polling and explicit cancellation |
| [`recipes/content-moderation/`](recipes/content-moderation/) | Risk-score UGC (`allow`/`flag`/`block` + score) with `output_type`, layered on the built-in AI Firewall |
| [`recipes/document-qa/`](recipes/document-qa/) | Grounded, cited answers over ingested documents with `knowledge_bindings` (and honest refusal on a miss) |
| [`recipes/customer-support/`](recipes/customer-support/) | An agent, imported as an employee bundle, that answers from a KB **and** calls a Mode B custom-tool webhook for live order status, with guardrails on |

### Vertical worked examples

| Recipe | What it shows |
|---|---|
| [`recipes/legaltech/`](recipes/legaltech/) | Contract clause extraction with structured output + a Mode B custom-tool webhook for partner-side precedent lookup |
| [`recipes/healthcare/`](recipes/healthcare/) | Clinical-note triage with `output_type` JSON-schema validation + per-patient memory isolation (`X-Canonical-User`) |
| [`recipes/finance/`](recipes/finance/) | 10-K filing diff using the async-job pattern for long documents, with `search_web` for live market-data enrichment |

## Common prerequisites (recipes)

```bash
python -m pip install -r requirements-dev.txt
export LIBRA_OS_URL=https://nova.your-company.example
export LIBRA_OS_API_KEY=msk_live_...
```

Each recipe's `README.md` lists vertical-specific extras (FastAPI for the legaltech webhook, etc.).

## Sample data

All sample inputs are **synthetic**. The legaltech MSA, the healthcare clinical note, and the finance 10-K excerpts are constructed for documentation — they don't correspond to real contracts, real patients, or real filings. Replace them with your own data when adapting.

## Versioning

The Python protocol suite pins SDK **2.0.0** and its direct test dependencies in
`requirements-dev.txt`. New examples list their runtime dependencies separately.
The local Compose environment defaults to kernel **v0.3.1**. The last live pass
across every example was on **v0.3.0** on October 29, 2026. The new default was
checked against the public release and registry, not rerun live. See the
[verification record](docs/validation.md) and the [November review](REVIEW-2026-11.md).

Report Runtime issues in the [public LibraOS issue tracker](https://github.com/libraos/community/issues).
