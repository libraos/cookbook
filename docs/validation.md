# Validation: contracts, Runtime boundaries and model behavior

Every core example needs an observable outcome and a failure/boundary check.
An expected-output screenshot is not a test. Passing a simulated HTTP test does
not prove the real Runtime implements its side of the contract.

## Offline protocol CI

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -m 'not live' --junitxml=test-results.xml
node --experimental-strip-types --test shared/mission-client/src/index.test.ts
```

The GitHub workflow runs without model keys or a kernel. It checks the real SDK's
serialization against HTTP fixtures, the callback verifier through an ASGI
transport, schema rejection, recovery handles and mission event reduction.
It uploads JUnit results. This suite is deterministic and suitable for PR gating.

## Coverage and remaining live checks

| Core case | Automated offline check | Live behavior / limitation |
|---|---|---|
| First Agent | Python path creates/chats, preserves history; 401/403 and model-service 503 propagate | Does not certify Bash/TypeScript parity or a provider's availability |
| Ticket Routing | Malformed JSON/schema rejected; a schema-valid wrong class is counted as a miss | Label accuracy is a model evaluation, separate from schema validity |
| Document Q&A | Bound collection and grounding system prompt sent; in-scope and miss inputs exercised; auth failure propagates | Correct source attribution and non-fabrication still need live evidence; fixtures are not retrieval tests |
| Tool Calling | Signed callback, known/missing order, rejected signature, duplicate callback, HTTP/transport errors; registration forces the lookup, carries no secret and refuses a Runtime that drops the tool; answers outside the contract or without a matching recorded lookup raise | Opt-in known/missing tool calls require actual receipt evidence; separate stopped-webhook evaluation. Kernel v0.3.0 or later |
| Memory | Separate tokens, fresh conversation IDs, no forwarded history, identity preflight, conversation-access responses | Opt-in A conversation read/B denial, plus positive recall and cross-user/override isolation; probabilistic recall is not a complete authorization audit |
| Async Job | Persisted idempotency/ID, uncertain submit, resume, timeout, cancellation race, terminal states and read failures | Opt-in submit/resume/completion; actual kernel restart durability is outside this client's proof |
| Mission Decision | Pending gate, reducer failure, replay, 403 from decision endpoint | Server-side ownership/role matrix still requires a named Runtime integration test |
| Tool Action Approval | Not implemented as a standalone tutorial yet | Approval/rejection/permission and exactly-once side effects tracked in the core repository |
| Marketing Mission | Stream replay/reconnect, event dedup, pending decision, report and failure states | Full mission/model run remains separate from client protocol tests |

Customer Support and Legaltech use the bundle registration workaround validated
in [PR #14](https://github.com/libraos/cookbook/pull/14). The REST registration
contract still has a [follow-up task](https://github.com/libraos/libraos/issues/1729).

## Opt-in Runtime/model evaluation

Tests marked `live` are skipped unless `COOKBOOK_LIVE=1`, even when tokens happen
to be present. Configure only the selected recipe's prerequisites, then run:

```bash
COOKBOOK_LIVE=1 python -m pytest tests/test_live.py -k memory --junitxml=live-results.xml
COOKBOOK_LIVE=1 python -m pytest tests/test_live.py -k tool_lookup --junitxml=live-results.xml
COOKBOOK_LIVE=1 python -m pytest tests/test_live.py -k async --junitxml=live-results.xml
```

Use a disposable environment: live runs create agents/jobs and may incur model
usage. Do not run every live case together when intentionally stopping the tool
webhook. Follow that recipe's separate unavailable-service command.

Assert JSON structure, state changes, unique recall markers and callback
receipts. Do not compare exact natural-language responses. Repeat behavioral
evaluations across seeds/inputs and report pass rates with the model, Runtime
version, SDK version and feature configuration; one successful run is not a
quality benchmark. Missing prerequisites are errors when a live case is selected,
not silently successful evaluations.

For Q&A evaluation, separately label whether the question is answerable, the
acceptable supporting documents, required facts and prohibited invented facts.
An evaluator should assess source support and refusal semantics, not insist on
one refusal phrase. This model-quality evaluation is not yet automated here.

## Verification record — 2026-10-29 (Tool Calling)

- Kernel **v0.3.0** (`52cb8d7b`), fresh Compose volumes, MegaNova gateway, SDK 2.0.0.
  The recipe now registers its agent through `POST /v1/agents` instead of an
  app manifest; v0.2.2–v0.2.4 never offered `custom_tools` to the model.
- `gemini/gemini-2.5-flash`: documented runs pass; `tool_lookup` live test
  passes; **20/20** lookups (10 per order) returned the typed status with
  exactly one matching callback receipt; `webhook_unavailable` passed 3/3,
  answering `unavailable`.
- `mistralai/Mistral-Small-3.2-24B-Instruct-2506`: **9/20**. Of the 11
  failures, 10 were malformed tool arguments (`ORD-5591,`, `ORD-NOTFOUND`, long
  random suffixes), each rejected by the client's check against the recorded
  lookup, and 1 ran to the client timeout. No run printed a status the tool did
  not return. The same request sent straight to the gateway reproduces the
  malformed arguments (13/16 clean), while Gemini 2.5 Flash, Qwen3-235B and
  Mistral-Small-4 return 16/16 clean arguments.
- Kernel **v0.2.2**: `tool_calling.py` stops at registration with "requires
  kernel v0.3.0 or later" (`POST /v1/agents` answers 426).
- Offline: 55 Python tests passed, 9 mission client tests passed.

## Verification record — 2026-10-16

- Offline results after local integration: **36 Python tests passed**, **9 mission
  client tests passed**, **4 live evaluations skipped** by explicit opt-in policy.
- Environment used for the new Python protocol suite: Python 3.12, SDK 2.0.0,
  direct dependencies pinned in `requirements-dev.txt`.
- Mission client: Node 24 locally; CI targets Node 22 with type stripping.
- New P0 live Runtime/model runs: **not performed**. No Runtime release is
  certified by the mocked tests.
- Common Compose default: kernel v0.2.2. Record `/api/version` when running live;
  do not treat that default as evidence of feature parity with current source.
- Async issue #1708: closed when checked; HTTP example retains native shapes.
- Baseline integration: [PR #12](https://github.com/libraos/cookbook/pull/12),
  [PR #13](https://github.com/libraos/cookbook/pull/13),
  [PR #14](https://github.com/libraos/cookbook/pull/14) and
  [PR #15](https://github.com/libraos/cookbook/pull/15) report v0.2.2 live checks
  for original examples. Those reported runs are distinct from this branch's
  offline tests and do not validate the three newly added P0 recipes.

For a new recipe, include level, prerequisites, dependencies, feature flags,
observable result, failure/boundary tests, cleanup, verification status and the
next learning step. Track implementation work in
[`libraos/libraos`](https://github.com/libraos/libraos/issues/1726).
