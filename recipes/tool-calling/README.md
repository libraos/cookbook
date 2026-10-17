# Tools — signed order lookup

**L2, independent branch.** Prerequisite: First Agent. You do not need Document
Q&A, memory, browser sign-in or a mission. This adds one read-only tool over two
synthetic outcomes: a known order and a missing order.

**Validation status:** offline callback/client protocol tests pass; live Runtime
and model evaluation must be run on your selected release. See
[the verification record](../../docs/validation.md).

## Run

Use [shared setup](../../docs/recipe-setup.md), or install `requirements.txt` in
this directory. This example uses Python 3.12, SDK 2.0.0's webhook verifier and
the native app chat HTTP endpoint. It inherits the Runtime's model; that model
must support tool calls and structured output.

From the repository root, choose a local demo secret and start the Compose
environment with the tool overlay:

```bash
export LIBRA_OS_CALLBACK_SECRET_COOKBOOK="$(openssl rand -hex 32)"
docker compose --env-file get-started/.env \
  -f get-started/docker-compose.yml -f recipes/tool-calling/compose.yaml up -d
cd recipes/tool-calling
python webhook_server.py
```

The overlay mounts the agent manifest and permits **only the explicit local
development callback host**. The same secret must be in the kernel and webhook
process; it is not sent in the agent definition. Run the webhook on the Docker
host. `host.docker.internal:8080` is resolved by the kernel container, not by a
remote hosted Runtime. For a remote deployment, change the agent callback URL to
your reachable HTTPS service and configure its host policy and secret reference.

Port 8080 taken? Set `COOKBOOK_WEBHOOK_PORT` for both the webhook and
`docker compose` (the overlay reads it for the allowed host), and change
`callback.url` in `libraos-app/agents/cookbook-order-lookup.md` to the same
port. The webhook listens on every interface by default, because on Linux the
kernel reaches it through the Docker bridge; set `COOKBOOK_WEBHOOK_HOST` to the
bridge address (usually `172.17.0.1`) to narrow it.

In a second terminal, obtain `LIBRA_OS_API_KEY` using shared setup, activate the
same Python environment, then from the repository root install the mounted app:

```bash
python - <<'PY'
import os, httpx
r = httpx.post(os.environ['LIBRA_OS_URL'] + '/v1/apps/cookbook-tools/install',
    headers={'Authorization': 'Bearer ' + os.environ['LIBRA_OS_API_KEY']})
r.raise_for_status()
result = r.json()
assert result.get('status') == 'active' and result.get('agents_registered') == 1, result
print('Installed one tool agent')
PY
python recipes/tool-calling/tool_calling.py ORD-5591
python recipes/tool-calling/tool_calling.py ORD-NOT-FOUND
```

The answer contains typed `order_id` and `status`. The webhook writes
`receipts.jsonl` in its working directory: a signed callback must appear there
for each lookup. An answer that happens to mention UPS is not proof of a tool call.

The manifest path is intentional: the REST custom-tool registration contract
used by older recipes is being [verified separately](https://github.com/libraos/libraos/issues/1729).
Do not replace nested `callback.url/auth` with an assumed `callback_url` field.

## Observable checks

| Scenario | Protocol test | Live model/Runtime check |
|---|---|---|
| Known order | Signed POST returns `found: true` and a stringified JSON output | Typed `in_transit` answer **and** a new callback receipt |
| Missing order | Signed POST returns `found: false` | Typed `not_found` answer and receipt |
| Invalid signature | HTTP 401; handler creates no receipt | No model required |
| Duplicate delivery | Same result; one receipt | In-memory dedup only, not a durable production guarantee |
| Webhook unavailable | Client propagates upstream/transport failure | Stop webhook; Runtime returns a tool/upstream failure or typed `unavailable`, never an invented status |

```bash
# From repository root; no Runtime/model needed.
python -m pytest tests/test_tool_calling.py

# With webhook and Runtime running:
export COOKBOOK_TOOL_RECEIPTS="$PWD/recipes/tool-calling/receipts.jsonl"
COOKBOOK_LIVE=1 python -m pytest tests/test_live.py -k tool_lookup --junitxml=live-results.xml

# Stop ONLY the demo webhook first. This is a separate live evaluation.
COOKBOOK_LIVE=1 COOKBOOK_WEBHOOK_UNAVAILABLE=1 \
  python -m pytest tests/test_live.py -k webhook_unavailable --junitxml=live-results.xml
```

The fixture is not a real order system and does not implement customer/order
authorization. An ISV backend must authorize each order access independently of
webhook signature verification. Next: [Customer Support](../customer-support/)
adds knowledge and identity; [approvals](../../docs/approval-mechanisms.md) cover
mutating actions as a separate mechanism.

Stop the webhook and remove its local receipts when finished. The overlay is a
local demonstration; it does not install a public webhook service.
