# Customer support — answer from a KB and take actions

End-to-end worked example: a support agent that answers product and policy questions from your knowledge base *and* calls back into your systems (order status, quotes, lookups) via a Mode B custom tool — the two together are what makes it a support agent rather than a FAQ bot.

## What this demonstrates

- **Knowledge grounding** — `knowledge_bindings: ["support-kb"]` scopes the agent's retrieval to your ingested policies/FAQs, so answers cite your documents instead of the model's training data.
- **Mode B custom tool (`order_lookup`)** — the agent decides, per turn, whether to answer from the KB or fetch live data. When it needs live data LibraOS POSTs a signed payload to the tool's `callback.url`; `webhook_server.py` (FastAPI) verifies the HMAC signature (`X-LibraOS-Signature`, with the older `X-Nova-Signature` as fallback) and returns the order status. Replace the toy `_ORDER_DB` with your real OMS.
- **Agent defined as an employee bundle** — custom tools live in the agent definition file (`custom_tools:` frontmatter), so the script builds the employee + agent as a bundle zip in memory and imports it with `POST /v1/managed/employees/bundle/import` — the same format `employees/{id}/bundle/export` produces. From kernel v0.3.0, `POST /v1/agents` also takes `custom_tools` (see [Tools](../tool-calling/)) and a bundle import loads its agents at once; the bundle keeps the agent and its owning employee together.
- **Guardrails on** — a support agent handles untrusted customer text, so the inbound **AI Firewall** (prompt-injection / abuse, on by default) and the outbound **PII redactor** stay on. The redactor is off by default from kernel v0.3.0, so the agent declares `guardrails: {pii_redactor: enabled}`.
- **Per-customer memory scoping** — the `X-Canonical-User` header carries your stable customer id, so one customer's context never bleeds into another's session. `X-End-User` (the SDK's `end_user=`) is **not** enough: all end users of one service credential share a single memory log per agent (verified on kernel v0.2.2 and v0.3.0). The header is honoured only for an admin-owned credential; on v0.3.0 an API key also needs `"allow_impersonation": true`. The script calls the native chat endpoint because the SDK's `messages.create` cannot set it.

## Files

| File | Role |
|---|---|
| `support_agent.py` | Ingests the KB, registers the persona (KB + tool), asks a KB question and an action question |
| `webhook_server.py` | FastAPI server hosting the `order_lookup` tool callback (HMAC-verified) |
| `sample_support_kb.md` | Synthetic support KB (refunds, shipping, warranty, billing) |

## Run

Tested against kernel v0.3.0 with `libraos-sdk` 2.0.0.

**On the LibraOS host** — the kernel signs callbacks with a secret it holds itself, named by the tool's `secret_ref`, and only sends them to hosts it is allowed to:

```bash
LIBRA_OS_CALLBACK_SECRET_SUPPORT=<webhook secret>          # the secret_ref this recipe uses
LIBRA_OS_CALLBACK_ALLOWED_HOSTS=partner.example             # host(s) of LIBRA_OS_CB_URL (https)
```

**On your side:**

```bash
pip install 'libraos-sdk>=2.0.0' fastapi uvicorn
export LIBRA_OS_URL=https://nova.your-company.example
export LIBRA_OS_API_KEY=msk_live_...
export LIBRA_OS_CB_SECRET=<webhook secret>                  # same value as LIBRA_OS_CALLBACK_SECRET_SUPPORT
export LIBRA_OS_CB_URL=https://partner.example/nova/cb/      # public URL of webhook_server.py

# terminal 1 — the tool host
uvicorn webhook_server:app --port 8080

# terminal 2 — the agent
python support_agent.py
```

```
Imported bundle: {'employee_id': 'support-team', 'agents_imported': 1}

[cust-1042] Q: What's your refund window, and are digital downloads refundable?
A: Our refund window is 30 days from the date of purchase. Digital downloads are
   non-refundable once downloaded. Source: doc-7545c443cb1a7d6d

[cust-1042] Q: Where is my order ORD-5591? It still hasn't arrived.
A: Your order ORD-5591 is in transit with UPS (tracking 1Z999AA10123456784),
   estimated to arrive 2026-07-04.
```

Terminal 1 logs one `POST /nova/cb/...` per tool call; that line is the smoke check that the callback arrived and its signature verified (a bad signature is a 401 there and a "tool failed" answer here).

> **Local testing:** `LIBRA_OS_CB_URL` must be reachable *from LibraOS*, and the kernel refuses plain `http://` and loopback targets unless the host is listed in `LIBRA_OS_CALLBACK_DEV_HOSTS` (e.g. `localhost:8080`). For a remote kernel, expose `webhook_server.py` with a tunnel (ngrok/cloudflared) and set `LIBRA_OS_CB_URL` to the tunnel URL. The API key must be allowed to import employee bundles (an admin token is).

## Adapting to your data

- **Real KB.** Replace `sample_support_kb.md` with your actual help-centre content, or upload files with `c.documents.upload(...)`. See the [`document-qa`](../document-qa/) recipe for retrieval tuning.
- **Real tools.** Point `_ORDER_DB` at your OMS. Add more tools (issue a refund, create a ticket, check inventory) by appending to `CUSTOM_TOOLS` and adding a matching `@router.tool(...)` handler. High-risk, side-effecting tools can be gated behind the dry-run / approval flow (`LIBRA_OS_PENDING_ACTIONS_ENABLED`).
- **Different secret name.** `LIBRA_OS_CB_SECRET_REF` overrides the `secret_ref` (default `LIBRA_OS_CALLBACK_SECRET_SUPPORT`); the kernel only signs with variables in its `LIBRA_OS_CALLBACK_SECRET_*` namespace or an explicit `LIBRA_OS_CALLBACK_SECRET_REFS` allowlist.
- **Relax PII redaction only where a workflow needs raw names.** This agent enables the redactor explicitly; remove that line (or set `guardrails.pii_redactor: disabled`) *only* on an agent whose job legitimately handles raw customer identifiers.
- **Streaming.** For a progressive chat UI, the HTTP surface streams token deltas (`stream=true` on `POST /v1/chat/completions`, or `metadata.stream_events` on the native chat endpoint). Use a streaming model (`gpt-*`, `claude-*`) for smooth output.

## Prose companion

The LibraOS docs guide walks the full build (knowledge + tools + guardrails + streaming) with decision criteria and success metrics: **https://docs.meganova.ai → LibraOS → Use Cases → Customer Support Agent**.
