"""Document Q&A — grounded, cited answers over your own documents.

End-to-end partner-side script:
    1. Ingests a few policy documents into a knowledge collection.
    2. Creates a persona agent bound to that collection: every turn retrieves
       from it and the retrieved passages are injected into the prompt.
    3. Asks a question the documents answer (grounded, cited) and one they do
       NOT (the agent should decline rather than fabricate).

The prose companion (collection setup, retrieval tuning, the knowledge gate)
lives in the LibraOS docs:
https://docs.meganova.ai → LibraOS → Use Cases → Document Q&A Copilot.

Prerequisites::

    pip install libraos-sdk
    export LIBRA_OS_URL=https://nova.your-company.example
    export LIBRA_OS_API_KEY=msk_live_...

Run::

    python document_qa.py
"""

from __future__ import annotations

import asyncio
import contextlib
import os

import httpx
from libraos import Client
from libraos.errors import NotFoundError


COLLECTION = "employee-handbook"

# In a real deployment you'd upload PDFs/DOCX with `c.documents.upload(...)`;
# here we ingest a few short text docs inline so the recipe is self-contained.
# LibraOS chunks, embeds, and indexes each one automatically.
DOCS: list[dict] = [
    {
        "title": "pto-policy",
        "content": (
            "Paid time off (PTO) accrues at 1.5 days per month for full-time employees, "
            "up to a cap of 30 days. Unused PTO above the cap is forfeited at year end. "
            "PTO requests must be submitted at least two weeks in advance for absences "
            "longer than three consecutive days."
        ),
    },
    {
        "title": "expense-policy",
        "content": (
            "Business expenses under 75 USD may be reimbursed without a receipt. Expenses "
            "of 75 USD or more require an itemised receipt uploaded within 30 days. "
            "Alcohol is reimbursable only as part of a client meal, capped at 50 USD per head."
        ),
    },
    {
        "title": "remote-work-policy",
        "content": (
            "Employees may work remotely up to three days per week by default. Fully-remote "
            "arrangements require director approval and a signed home-office safety attestation. "
            "Core collaboration hours are 10:00–15:00 in the employee's home timezone."
        ),
    },
]


async def ask(c: Client, question: str) -> None:
    resp = await c.messages.create(
        agent_id="handbook-copilot",
        messages=[{"role": "user", "content": question}],
    )
    text = resp.text
    print(f"\nQ: {question}\nA: {text}")


async def recreate_collection(base_url: str, api_key: str) -> None:
    """Start the collection over, registered so an agent can be bound to it.

    Before kernel v0.3.0, ingest created a collection that search could use but
    not one an agent could be bound to: the binding was dropped with only a
    log line (libraos/libraos#615, fixed by #1732). Deleting and creating it
    also starts each run from an empty collection. The SDK has no call for
    this yet, so it is one admin HTTP request.
    """
    headers = {"authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(base_url=base_url, headers=headers, timeout=60) as h:
        r = await h.delete(f"/api/knowledge/collections/{COLLECTION}")
        if r.status_code not in (200, 204, 404):
            r.raise_for_status()
        r = await h.post("/api/knowledge/collections", json={"name": COLLECTION, "access_level": "corporate"})
        r.raise_for_status()


async def main() -> None:
    base_url = os.environ.get("LIBRA_OS_URL", "https://nova.your-company.example")
    api_key = os.environ["LIBRA_OS_API_KEY"]

    async with Client(base_url=base_url, api_key=api_key, timeout=180) as c:
        # Start clean: a run that failed part-way leaves this behind, and the
        # create call below would then fail with 409.
        with contextlib.suppress(NotFoundError):
            await c.agents.delete("handbook-copilot")

        # 1. Ingest the documents into a freshly created collection, so a
        #    second run does not index them twice.
        await recreate_collection(base_url, api_key)
        for doc in DOCS:
            await c.knowledge.ingest(
                content=doc["content"], title=doc["title"], collection=COLLECTION
            )
        print(f"Ingested {len(DOCS)} docs into '{COLLECTION}'.")

        # 2. A persona bound to the collection. Retrieval is scoped to the
        #    bound collection and the hits are injected into every turn.
        #    tool_scope="none": the copilot answers from the injected passages
        #    and needs no catalog tools (a persona without a scope is offered
        #    the whole catalog, which only slows the answer down).
        await c.agents.create(
            id="handbook-copilot",
            type="persona",
            brain=True,
            tool_scope="none",
            knowledge_bindings=[COLLECTION],
            system=(
                "You are an HR handbook copilot. Answer ONLY from the retrieved handbook "
                "passages and cite the source for each fact. If the handbook does not cover "
                "the question, say so plainly — never guess a policy or invent a number."
            ),
        )

        # 3a. Grounded — the handbook covers this.
        await ask(c, "How much PTO do I accrue per month, and is there a cap?")
        await ask(c, "Do I need a receipt for a 60 dollar expense?")

        # 3b. Out of scope — the handbook says nothing about this. A good answer
        #     declines instead of fabricating a plausible-sounding policy.
        await ask(c, "What is the company's parental leave policy?")

        # The agent stays, so you can inspect it and its binding; the next run
        # starts clean.
        print(f"\nAgent 'handbook-copilot' is bound to {COLLECTION!r}.")


if __name__ == "__main__":
    asyncio.run(main())
