# Customer support — answer from a KB and take actions

End-to-end worked example: a support persona that answers product and policy questions from your knowledge base *and* calls back into your systems (order status, quotes, lookups) via a Mode B custom tool — the two together are what makes it a support agent rather than a FAQ bot.

## What this demonstrates

- **Knowledge grounding** — `knowledge_bindings=["support-kb"]` scopes the agent's retrieval to your ingested policies/FAQs, so answers cite your documents instead of the model's training data.
- **Mode B custom tool (`order_lookup`)** — the agent decides, per turn, whether to answer from the KB or fetch live data. When it needs live data it POSTs a signed payload to your `callback_url`; `webhook_server.py` (FastAPI) verifies the HMAC signature and returns the order status. Replace the toy `_ORDER_DB` with your real OMS.
- **Guardrails on by default** — a support agent handles untrusted customer text, so the inbound **AI Firewall** (prompt-injection / abuse) and the outbound **PII redactor** stay on. You don't configure anything to get them.
- **Per-customer memory scoping** — the `X-End-User` header carries your stable customer id, so one customer's context never bleeds into another's session.

## Files

| File | Role |
|---|---|
| `support_agent.py` | Ingests the KB, registers the persona (KB + tool), asks a KB question and an action question |
| `webhook_server.py` | FastAPI server hosting the `order_lookup` tool callback (HMAC-verified) |
| `sample_support_kb.md` | Synthetic support KB (refunds, shipping, warranty, billing) |

## Run

```bash
pip install nova-os-sdk fastapi uvicorn
export NOVA_OS_URL=https://nova.your-company.example
export NOVA_OS_API_KEY=msk_live_...
export NOVA_CB_SECRET=change-me
export NOVA_CB_URL=https://partner.example/nova/cb   # public URL of webhook_server.py

# terminal 1 — the tool host
uvicorn webhook_server:app --port 8080

# terminal 2 — the agent
python support_agent.py
```

```
[cust-1042] Q: What's your refund window, and are digital downloads refundable?
A: Our refund window is 30 days from purchase. Digital goods are non-refundable
   once downloaded [support-policies].

[cust-1042] Q: Where is my order ORD-5591? It still hasn't arrived.
A: Your order ORD-5591 is in transit with UPS (tracking 1Z999AA10123456784),
   estimated to arrive 2026-07-04.
```

> **Local testing:** `NOVA_CB_URL` must be reachable *from Nova OS*. For local dev, expose `webhook_server.py` with a tunnel (ngrok/cloudflared) and set `NOVA_CB_URL` to the tunnel URL.

## Adapting to your data

- **Real KB.** Replace `sample_support_kb.md` with your actual help-centre content, or upload files with `c.documents.upload(...)`. See the [`document-qa`](../document-qa/) recipe for retrieval tuning.
- **Real tools.** Point `_ORDER_DB` at your OMS. Add more tools (issue a refund, create a ticket, check inventory) by appending to `CUSTOM_TOOLS` and adding a matching `@router.tool(...)` handler. High-risk, side-effecting tools can be gated behind the dry-run / approval flow (`NOVA_OS_PENDING_ACTIONS_ENABLED`).
- **Relax PII redaction only where a workflow needs raw names.** The redactor is on by default; disable it (`guardrails.pii_redactor: disabled`) *only* on a persona whose job legitimately handles raw customer identifiers, never platform-wide.
- **Streaming.** For a progressive chat UI, the HTTP surface streams token deltas (`stream=true` on `POST /v1/chat/completions`, or `metadata.stream_events` on the native chat endpoint). Use a streaming model (`gpt-*`, `claude-*`) for smooth output.

## Prose companion

The Nova OS docs guide walks the full build (knowledge + tools + guardrails + streaming) with decision criteria and success metrics: **https://docs.meganova.ai → Nova OS → Use Cases → Customer Support Agent**.
