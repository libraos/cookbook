# Ticket routing — classify support tickets into a validated intent

End-to-end worked example: a partner sends raw ticket text to a classifier agent and gets back a typed `{reasoning, intent}` verdict that drives a routing rule — no ML infrastructure, no labelled training set required to start.

## What this demonstrates

- **`output_type` JSON-schema validation** — every classification is validated server-side against an enum contract before it leaves Nova OS. Your routing logic acts on `intent`; you never parse free text or handle a model that invents a category.
- **`violation_mode=repair`** — if the first reply doesn't conform, Nova OS re-prompts once with the schema in the system prompt instead of returning a 422. For a high-volume classifier that one bounded retry is cheaper than error handling on your side.
- **`brain=false`** — classification is one short call: one ticket in, one verdict out. Skipping the planner keeps it on the fast, cheap skill tier at ~a second per ticket.
- **An accuracy eval loop** — the gate you run against a hand-labelled set *before* pointing live traffic at the classifier, plus the miss-analysis habit that tells you exactly what to fix.

## Files

| File | Role |
|---|---|
| `ticket_routing.py` | Registers the classifier, runs a labelled set through it, reports accuracy |
| `sample_tickets.jsonl` | 10 labelled tickets (`{"ticket": ..., "expected": ...}`) as a starter validation set |

## Run

```bash
pip install nova-os-sdk
export NOVA_OS_URL=https://nova.your-company.example
export NOVA_OS_API_KEY=msk_live_...
python ticket_routing.py
```

You'll see a per-ticket pass/fail line and a final accuracy figure:

```
✓ expected=Security             got=Security             :: Someone just logged into my account from a device …
✗ expected=Account management   got=Product information  :: Why did my subscription renew without any warning …
    reasoning: The user is asking a question about subscription behaviour …

Accuracy: 9/10 = 90%
```

## Adapting to your data

- **Replace the taxonomy.** Edit the `enum` in `INTENT_SCHEMA` to match your support workflow. Update a category description, not a trained model, when your categories evolve.
- **Grow the validation set.** Ten tickets is a smoke test; validate on 200–500 hand-labelled tickets before live traffic. Track accuracy, and read the `reasoning` on every miss — misses cluster into *wrong category description*, *ambiguous ticket text*, or a *genuine edge case*, and each points at a different fix.
- **Add fields.** Extend the schema with `urgency` (`low|medium|high|critical`) or `secondary_intent` if your routing needs them. Keep each field a narrow enum — an enum with `repair` is far more reliable than a free-text score.
- **Large taxonomies (20+ categories).** A single classifier degrades as the enum grows. Split into a top-level router agent + a sub-classifier agent per branch; your integration calls the top level first, then dispatches to the matching sub-classifier. One extra call, materially higher accuracy.
- **Few-shot from your own tickets.** Ingest labelled examples as a knowledge collection and add `knowledge_bindings=["ticket-examples"]` to the agent — Nova OS injects the nearest labelled examples for each incoming ticket automatically (see the [`document-qa`](../document-qa/) recipe for the ingest pattern).

## Prose companion

The Nova OS docs guide covers the decision ("should you use an LLM for routing?"), success criteria, and integration patterns (push webhook vs pull batch): **https://docs.meganova.ai → Nova OS → Use Cases → Ticket Routing**.
