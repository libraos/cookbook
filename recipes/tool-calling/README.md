# Tools — signed order lookup

**L2, independent branch.** Prerequisite: First Agent. You do not need Document
Q&A, memory, browser sign-in or a mission. This adds one read-only tool over two
synthetic outcomes: a known order and a missing order.

**Requires kernel v0.3.0 or later.** Earlier kernels refuse this recipe's
`POST /v1/agents` (426, a beta-header gate) or, with the beta header, accept it
while dropping `custom_tools`. On v0.2.x the app-manifest route this recipe used
before never offered custom tools to a persona either, so the model received no
tools at all. `tool_calling.py` stops with "requires kernel v0.3.0 or later" in
both cases.

**Validation status:** offline callback/client protocol tests pass. Live on
v0.3.0 through the MegaNova gateway: 20/20 with `gemini/gemini-2.5-flash`, 9/20
with `mistralai/Mistral-Small-3.2-24B-Instruct-2506`, whose tool arguments are
often malformed even when called directly. See
[the verification record](../../docs/validation.md). Run it on your selected
release and model.

## Run

Use [shared setup](../../docs/recipe-setup.md), or install `requirements.txt` in
this directory. This example uses Python 3.12, SDK 2.0.0's webhook verifier and
the native agent chat HTTP endpoint. It inherits the Runtime's model; that model
must support tool calls.

From the repository root, choose a local demo secret and start the Compose
environment with the tool overlay:

```bash
export LIBRA_OS_CALLBACK_SECRET_COOKBOOK="$(openssl rand -hex 32)"
LIBRAOS_VERSION=v0.3.0 docker compose --env-file get-started/.env \
  -f get-started/docker-compose.yml -f recipes/tool-calling/compose.yaml up -d
cd recipes/tool-calling
python webhook_server.py
```

The overlay permits **only the explicit local development callback host**. The
same secret must be in the kernel and webhook process; the agent definition
names it (`secret_ref`) but never carries it. Run the webhook on the Docker
host: `host.docker.internal:8080` is resolved by the kernel container, not by a
remote hosted Runtime. For a remote deployment, set `COOKBOOK_CALLBACK_URL` to
your reachable HTTPS service and configure its host policy and secret reference.

Port 8080 taken? Set `COOKBOOK_WEBHOOK_PORT` for the webhook, for
`docker compose` (the overlay reads it for the allowed host) and for
`tool_calling.py` (it builds the callback URL from it). The webhook listens on
every interface by default, because on Linux the kernel reaches it through the
Docker bridge; set `COOKBOOK_WEBHOOK_HOST` to the bridge address (usually
`172.17.0.1`) to narrow it.

In a second terminal, obtain `LIBRA_OS_API_KEY` using shared setup, activate the
same Python environment, then from the repository root:

```bash
python recipes/tool-calling/tool_calling.py ORD-5591
python recipes/tool-calling/tool_calling.py ORD-NOT-FOUND
```

Each run registers `cookbook-order-lookup` through `POST /v1/agents` (a repeat
POST replaces the definition) and prints typed `order_id` and `status`. The
client accepts that status only when the turn's `tool_transcript` shows an
`order_lookup` call for exactly that `order_id` whose recorded result supports
it. The webhook writes `receipts.jsonl` in its working directory: a signed
callback must appear there for each lookup. An answer that happens to mention
UPS is not proof of a tool call.

Keep the callback nested as `callback.url` and `callback.auth`; do not replace
it with an assumed `callback_url` field. `POST /v1/agents` refuses unknown
fields with 400 `unsupported_field` from v0.3.0.

## Why the agent is defined this way

Each setting below fixes a failure observed in a live run on v0.3.0:

- **`tool_choice: order_lookup`** forces the first model call to be the lookup.
  Without it the model sometimes answered with an invented status and no
  callback.
- **`no_memory: true` on each chat** keeps observational memory out of the
  turn. Memory is one log per signed-in identity and agent, and it records
  questions and answers but not tool results. Earlier answers, including wrong
  ones, were recalled into later lookups and repeated by the model. A stateless
  lookup should not read or write that log.
- **No `output_type`.** On an OpenAI-compatible gateway the kernel enforces
  `output_type` by adding the schema to the system prompt for the whole turn,
  including the forced tool call. The model then mixed the answer's fields into
  the tool arguments (`"ORD-5591\n\nstatus: unavailable"`) or kept generating
  until the request timed out. The prompt asks for JSON only after the tool has
  run, and `tool_calling.py` checks that contract itself.
- **`brain: false`, `tool_scope: "none"`.** The agent can call `order_lookup`
  and nothing else from the tool catalog.
- **The answer must match the recorded lookup.** Each chat asks for
  `include_metadata`, and the client compares the status with the
  `order_lookup` result in `tool_transcript`. A malformed argument such as
  `ORD-5591,` reaches the webhook as an unknown order; relaying that
  `not_found` for `ORD-5591` is rejected rather than printed. A delivered
  result outranks a failed retry; delivered results that disagree are rejected.
  Calls are matched to results by tool-call id, so a gateway that returns tool
  calls without ids fails this check even when the lookup ran.

## Observable checks

| Scenario | Protocol test | Live model/Runtime check |
|---|---|---|
| Known order | Signed POST returns `found: true` and a stringified JSON output | Typed `in_transit` answer **and** a new callback receipt |
| Missing order | Signed POST returns `found: false` | Typed `not_found` answer and receipt |
| Invalid signature | HTTP 401; handler creates no receipt | No model required |
| Duplicate delivery | Same result; one receipt | In-memory dedup only, not a durable production guarantee |
| Malformed or unsupported answer | Prose, extra fields, a different `order_id`, an unknown status, no recorded lookup, or a status the recorded result does not support raise | A failed run is reported, never turned into a status |
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

A single passing run is not a quality measure: repeat lookups and report the
pass rate with the model and kernel version. The fixture is not a real order
system and does not implement customer/order authorization. An ISV backend must
authorize each order access independently of webhook signature verification.
Next: [Customer Support](../customer-support/) adds knowledge and identity;
[approvals](../../docs/approval-mechanisms.md) cover mutating actions as a
separate mechanism.

Stop the webhook and remove its local receipts when finished. The overlay is a
local demonstration; it does not install a public webhook service.
