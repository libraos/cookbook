# Document Q&A — grounded, cited answers over your documents

End-to-end worked example: a partner ingests policy documents into a knowledge collection and gets a persona that answers questions strictly from them — with citations, and a plain "not covered" instead of a fabricated policy when the answer isn't there.

## What this demonstrates

- **Knowledge ingest + binding** — `c.knowledge.ingest(...)` indexes each document into a collection (created on first ingest); `knowledge_bindings=[...]` on the agent scopes retrieval to it. The persona only ever retrieves from what you bound it to.
- **`knowledge_gate`** — for a knowledge-bound persona, a *confident* retrieval hit is answered directly on the cheap tier (~sub-second) without waking the planner; a low-confidence miss **fails open** to the full pipeline. You get cheap latency on the common case without giving up the brain on the hard ones.
- **Grounded refusal** — the last question ("parental leave") isn't in the handbook. A correct answer declines rather than inventing a plausible policy. That behaviour is the whole point of grounding: "here's the source" beats "sounds right".

## Files

| File | Role |
|---|---|
| `document_qa.py` | Ingests inline handbook docs, registers the copilot, asks in-scope + out-of-scope questions |

The recipe ingests short text inline so it's self-contained. In a real deployment you'd upload the actual files with `c.documents.upload(...)` (PDF/DOCX/etc. — Nova OS extracts, chunks, embeds, and OCRs scanned pages automatically).

## Run

```bash
pip install nova-os-sdk
export NOVA_OS_URL=https://nova.your-company.example
export NOVA_OS_API_KEY=msk_live_...
python document_qa.py
```

```
Ingested 3 docs into 'employee-handbook'.

Q: How much PTO do I accrue per month, and is there a cap?
A: You accrue 1.5 days of PTO per month, capped at 30 days; unused PTO above the cap is forfeited at year end [pto-policy].

Q: What is the company's parental leave policy?
A: The handbook doesn't cover parental leave, so I can't state a policy from the available documents.
```

## Adapting to your data

- **Upload real documents.** Swap the inline `DOCS` for `c.documents.upload(...)` against your PDFs/DOCX. Richer source documents are the single biggest quality lever — ingest the actual policy texts, not summaries.
- **Tune retrieval for multi-document matters.** Operators can raise `NOVA_OS_RAG_TOP_K` (chunks injected per turn) so a fact living only in a second or third document isn't lost, and lower `NOVA_OS_RAG_VECTOR_THRESHOLD` to admit under-scoring but relevant chunks.
- **Tune the gate.** `knowledge_gate_min_score` (per agent) / `NOVA_OS_KNOWLEDGE_GATE_MIN_SCORE` sets how confident a retrieval hit must be to take the cheap path. Raise it to escalate more turns to the planner; lower it to answer more directly.
- **Keep the anti-fabrication instruction.** The "never guess a policy" line in the system prompt is load-bearing — it's what turns a miss into an honest "not covered" instead of a confident hallucination.

## Prose companion

The Nova OS docs guide covers collection setup, per-user scoping, and retrieval/grounding options: **https://docs.meganova.ai → Nova OS → Use Cases → Document Q&A Copilot**.
