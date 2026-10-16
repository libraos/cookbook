# Document Q&A — grounded, cited answers over your documents

End-to-end worked example: a partner ingests policy documents into a knowledge collection and gets a persona that answers questions strictly from them — with citations, and a plain "not covered" instead of a fabricated policy when the answer isn't there.

## What this demonstrates

- **Knowledge ingest + binding** — `c.knowledge.ingest(...)` indexes each document into a collection (created on first ingest); `knowledge_bindings=[...]` on the agent scopes retrieval to it. The persona only ever retrieves from what you bound it to, and the retrieved passages are injected into every turn.
- **`tool_scope="none"`** — the copilot answers from the injected passages and needs no catalog tools; a persona that declares no scope is offered the whole catalog, which only slows the answer down.
- **`knowledge_gate`** — for a knowledge-bound persona, a *confident* retrieval hit is answered directly on the cheap tier without waking the planner; a low-confidence miss **fails open** to the full pipeline. It is switched on per agent in the agent definition (`knowledge_gate: true` in an agent file or employee bundle, see the [`customer-support`](../customer-support/) recipe for the bundle pattern); kernel v0.2.2 does not take it on `c.agents.create(...)`, so this recipe runs on the standard persona path. The deployment-wide switch is `LIBRA_OS_KNOWLEDGE_GATE_ENABLED`.
- **Grounded refusal** — the last question ("parental leave") isn't in the handbook. A correct answer declines rather than inventing a plausible policy. That behaviour is the whole point of grounding: "here's the source" beats "sounds right".

## Files

| File | Role |
|---|---|
| `document_qa.py` | Ingests inline handbook docs, registers the copilot, asks in-scope + out-of-scope questions |

The recipe ingests short text inline so it's self-contained. In a real deployment you'd upload the actual files with `c.documents.upload(...)` (PDF/DOCX/etc. — LibraOS extracts, chunks, embeds, and OCRs scanned pages automatically).

## Run

Tested against kernel v0.2.2 with `libraos-sdk` 2.0.0.

```bash
pip install libraos-sdk
export LIBRA_OS_URL=https://nova.your-company.example
export LIBRA_OS_API_KEY=msk_live_...
python document_qa.py
```

```
Ingested 3 docs into 'employee-handbook'.

Q: How much PTO do I accrue per month, and is there a cap?
A: Full-time employees accrue 1.5 days of PTO per month, with a cap of 30 days. Unused PTO above the cap is forfeited at year end.
Source: doc-99ff150d7fa16222

Q: What is the company's parental leave policy?
A: I don't have the company's parental leave policy in the provided knowledge base. The available excerpts cover PTO, remote work, and business expenses only.
```

Citations are the ingested document ids. A smoke check: the first two answers carry a `Source:` line, and the third declines instead of stating a number of weeks.

## Adapting to your data

- **Upload real documents.** Swap the inline `DOCS` for `c.documents.upload(...)` against your PDFs/DOCX. Richer source documents are the single biggest quality lever — ingest the actual policy texts, not summaries.
- **Tune retrieval for multi-document matters.** Operators can raise `LIBRA_OS_RAG_TOP_K` (chunks injected per turn) so a fact living only in a second or third document isn't lost, and lower `LIBRA_OS_RAG_VECTOR_THRESHOLD` to admit under-scoring but relevant chunks.
- **Tune the gate.** `knowledge_gate_min_score` (per agent, in the agent definition) / `LIBRA_OS_KNOWLEDGE_GATE_MIN_SCORE` sets how confident a retrieval hit must be to take the cheap path. Raise it to escalate more turns to the planner; lower it to answer more directly.
- **Keep the anti-fabrication instruction.** The "never guess a policy" line in the system prompt is load-bearing — it's what turns a miss into an honest "not covered" instead of a confident hallucination.

## Prose companion

The LibraOS docs guide covers collection setup, per-user scoping, and retrieval/grounding options: **https://docs.meganova.ai → LibraOS → Use Cases → Document Q&A Copilot**.
