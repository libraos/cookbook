# Shared recipe environment

Use Python **3.12** for the documented test environment, Node **22.12+** for the
mission-client tests, and a disposable local Runtime. From the repository root:

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

Start the kernel as described in [get-started](../get-started/README.md).
The examples inherit the kernel's configured model unless they explicitly
declare a model cascade. Older industry recipes still declare their own model
names; configure those to match models your endpoint actually serves.

## Use the local quickstart token in Python examples

This is a laptop-only admin setup identity. From the repository root, load the
environment you configured, then exchange the existing quickstart client secret:

```bash
set -a
. get-started/.env
set +a
export LIBRA_OS_URL="http://localhost:${LIBRAOS_PORT:-8900}"
export LIBRA_OS_API_KEY="$(python - <<'PY'
import os, httpx
secret = os.environ['LIBRA_OS_SERVICE_CLIENTS'].split('=', 1)[1]
r = httpx.post(os.environ['LIBRA_OS_URL'] + '/oauth/token', json={
    'grant_type': 'client_credentials', 'client_id': 'quickstart', 'client_secret': secret,
})
r.raise_for_status()
print(r.json()['access_token'])
PY
)"
python get-started/01-first-agent/first-agent.py
```

The token stays in the shell environment. Do not put it in source, screenshots,
or job receipts. In an existing application, use the deployment's scoped service
identity; do not copy the quickstart admin identity into a browser.

## Normal-user tokens for the memory branch

Create two ordinary users in the local Runtime's admin UI, in the same
organization. They need permission to chat with the demo's public agent.
For the local password-login flow, obtain each token without putting passwords
on the command line:

```bash
export LIBRA_OS_USER_A_TOKEN="$(python scripts/local-user-token.py)"
export LIBRA_OS_USER_B_TOKEN="$(python scripts/local-user-token.py)"
```

Enter A's credentials for the first command and B's for the second. If the
deployment requires SSO/MFA, use its supported sign-in flow to obtain normal-user
access tokens instead. The memory preflight checks `/oauth/userinfo`, rejects
admin identities and equal subjects, and checks that memory is enabled.

## Shared memory in the local kernel

The get-started Compose file turns observational memory on for the personal
assistant, and it applies to every agent. The kernel keeps one memory log per
canonical user and agent (within an org, and per `memory_scope` when an agent
sets one), and recalls observations condensed from earlier questions and
answers into later turns. The tool results behind those answers are not kept.
Two consequences for recipes:

- **Stateless recipes send `no_memory: true`.** Ticket Routing, Content
  Moderation, Legaltech and Tools classify or extract one input at a time. With
  memory on, earlier verdicts were recalled into later inputs and repeated: a
  wrong answer kept coming back, and Legaltech dropped the precedent scores its
  webhook had just returned.
- **Per-customer or per-patient memory needs `X-Canonical-User`.** All callers of
  one service credential share a single log, whatever `X-End-User` (the SDK's
  `end_user=`) says: customer B could recall customer A's details. Healthcare
  and Customer Support send `X-Canonical-User`, which gives each id its own log.
  Signed-in users (the personal assistant, the Memory recipe) are separated by
  their own tokens.

Before relying on `X-Canonical-User`:

- **It needs the impersonation capability, and fails silently without it.** An
  admin-owned credential has it; an API key minted on kernel v0.3.0 also needs
  `"allow_impersonation": true` (keys from earlier releases kept it). Without
  the capability the header is ignored, with no error, and every end user
  shares the credential's own log. Check once: two ids, one marker, as in the
  Memory recipe.
- **Every use is audited as impersonation.** The kernel logs
  `identity override: caller acted as another subject` with the id at WARN.
- **Ids share one namespace with real users.** A signed-in user's canonical id
  is their token subject, so an end-user id that equals one would read and write
  that user's memory. The recipes prefix theirs: `customer:…`, `patient:…`.

Document Q&A calls `/v1/messages` through the SDK, which keeps memory and has no
`no_memory` switch. Its answers were stable across repeated runs; a stateless
integration that sees earlier answers repeated should use native chat with
`no_memory`.

## Tests and cleanup

```bash
python -m pytest -m 'not live'
node --experimental-strip-types --test shared/mission-client/src/index.test.ts
```

No model key or running Runtime is needed for these tests. New receipts contain
task text and IDs, never bearer tokens, and are ignored by Git. Memory runs use
synthetic labels and delete their temporary agent; this is **not memory erasure**.
Reset the disposable environment when you need to erase its stored data.
See [validation](validation.md) before running optional live evaluations.
