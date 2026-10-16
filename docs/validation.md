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
| Tool Calling | Signed callback, known/missing order, rejected signature, duplicate callback, HTTP/transport errors | Opt-in known/missing tool calls require actual receipt evidence; separate stopped-webhook evaluation |
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

## Verification record — 2026-10-16

- Environment used for the new Python protocol suite: Python 3.12, SDK 2.0.0,
  direct dependencies pinned in `requirements-dev.txt`.
- Mission client: Node 24 locally; CI targets Node 22 with type stripping.
- New P0 live Runtime/model runs: **not performed**. No Runtime release is
  certified by the mocked tests.
- Common Compose default: kernel v0.2.2. Record `/api/version` when running live;
  do not treat that default as evidence of feature parity with current source.
- Async issue #1708: closed when checked; HTTP example retains native shapes.
- Baseline integration: [PR #12](https://github.com/libraos/cookbook/pull/12),
  [PR #13](https://github.com/libraos/cookbook/pull/13) and
  [PR #14](https://github.com/libraos/cookbook/pull/14) report v0.2.2 live checks
  for original examples. Those reported runs are distinct from this branch's
  offline tests and do not validate the three newly added P0 recipes.

For a new recipe, include level, prerequisites, dependencies, feature flags,
observable result, failure/boundary tests, cleanup, verification status and the
next learning step. Track implementation work in
[`libraos/libraos`](https://github.com/libraos/libraos/issues/1726).
