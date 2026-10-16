# Async jobs — submit, disconnect, recover

**L3, independent branch.** Prerequisite: First Agent and PostgreSQL-backed jobs.
No financial knowledge, web search, tool service or mission is needed. The input
is a short project-handover request; the recovery pattern also applies to longer
analyses, without artificially slowing this example down.

## Compatibility

This example deliberately uses **native HTTP**, not `Client.jobs`:

| Operation | Native route / shape |
|---|---|
| Submit | `POST /agents/v1/{agent}/jobs`, body `{message}`, header `Idempotency-Key` |
| Query | `GET /agents/v1/{agent}/jobs/{job_id}` |
| Cancel | `DELETE /agents/v1/{agent}/jobs/{job_id}` |
| State | `queued`, `running`, `done`, `failed`, `cancelled` |
| Output | `job_id`, `status`, optional `result` / `error` |

[#1708](https://github.com/libraos/libraos/issues/1708), originally recording the
SDK/Runtime route mismatch, was **closed** when checked on 2026-10-16. Current
Runtime source includes the managed route too. Older deployed releases may not.
Do not generalize the original Finance warning to every current SDK/Runtime
combination, or mix native `done`/`result` with managed response shapes. A future
SDK edition should verify the full create/get/cancel/status mapping on a named
release before switching this tutorial.

**Validation status:** offline HTTP contracts pass. Real Runtime execution and
durability on a tagged release remain to be recorded. The common Compose pin
alone is not live verification; check `/api/version` and idempotency support.

## Run

Use [shared setup](../../docs/recipe-setup.md), or install `httpx==0.28.1` with
Python 3.12. Run First Agent once so `first-assistant` exists. From this directory:

```bash
python async_jobs.py submit --receipt job-receipt.json
# Submission prints the Job ID and exits. Start another process later:
python async_jobs.py resume --receipt job-receipt.json --timeout 120
python async_jobs.py status --receipt job-receipt.json
```

The receipt is created **before** the POST and contains a fresh idempotency key,
Runtime URL, agent and message. Once accepted, the Job ID is atomically saved.
If the submit response is lost, `resume` reuses the exact payload/key; after the
Job ID is known, resume only queries the existing job. A receipt cannot silently
overwrite an earlier run or be used with another Runtime URL. Keep the same
authenticated principal for submission and recovery.

Client restart recovery is distinct from **kernel restart recovery**. This demo
tests the first. Durable server storage and execution checkpoint behavior need
their own live checks; it does not promise arbitrary work can resume after a
kernel crash or after the server's idempotency record expires.

## Failure and cancellation

```bash
# A local wait budget; it does not cancel the server's job.
python async_jobs.py resume --receipt job-receipt.json --timeout 0.1

# Cancel only when that is the intended action:
python async_jobs.py cancel --receipt job-receipt.json
```

`failed` and `cancelled` remain distinct terminal states. A completed job may
win the cancellation race; the script reads and prints the actual state after
the cancellation request. `status` and `cancel` never create a job. If submission
was uncertain and the receipt has no ID, they ask you to resume first.

Transient polling errors retry within the local wait budget. Invalid credentials,
forbidden access and missing jobs fail immediately. A timeout keeps the receipt
and returns a nonzero exit code. `failed` exits 1; `cancelled` exits 2.

## Verify

```bash
# From repository root. Includes lost reply, new-client resume, timeout,
# failed/cancelled states, cancellation race, read retry and auth failures.
python -m pytest tests/test_async_jobs.py

# Runtime and model required; first-assistant must exist.
COOKBOOK_LIVE=1 python -m pytest tests/test_live.py -k async --junitxml=live-results.xml
```

The live test checks submit/resume/completion. Failure/cancellation interleavings
are deterministic HTTP fixtures in CI, not forced model behavior. For an actual
cancellation test, submit a workload that remains queued/running long enough and
use `cancel`; a fast completed job returning `done` is not a failed cancellation
implementation.

Receipts contain task text but no credentials. After the job is terminal, remove
the local receipt if no longer needed. This does not delete the server's job.
Next: [Finance](../finance/) for a domain-specific input, or
[Marketing Mission](../../apps/digital-marketing-team/) for event replay and decisions.
