"""Document Q&A — grounded, cited answers over your own documents.

End-to-end partner-side script:
    1. Ingests a few policy documents into a knowledge collection.
    2. Creates a persona agent bound to that collection with `knowledge_gate`
       enabled — a confident retrieval hit is answered on the cheap tier without
       waking the planner; a miss fails open to the full pipeline.
    3. Asks a question the documents answer (grounded, cited) and one they do
       NOT (the agent should decline rather than fabricate).

The prose companion (collection setup, retrieval tuning, the knowledge_gate
score floor) lives in the Libra OS docs:
https://docs.meganova.ai → Libra OS → Use Cases → Document Q&A Copilot.

Prerequisites::

    pip install nova-os-sdk
    export NOVA_OS_URL=https://nova.your-company.example
    export NOVA_OS_API_KEY=msk_live_...

Run::

    python document_qa.py
"""

from __future__ import annotations

import asyncio
import os

from nova_os import Client


COLLECTION = "employee-handbook"

# In a real deployment you'd upload PDFs/DOCX with `c.documents.upload(...)`;
# here we ingest a few short text docs inline so the recipe is self-contained.
# Libra OS chunks, embeds, and indexes each one automatically.
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
        metadata={"agent_id": "handbook-copilot"},
    )
    text = resp.content if hasattr(resp, "content") else resp
    print(f"\nQ: {question}\nA: {text}")


async def main() -> None:
    base_url = os.environ.get("NOVA_OS_URL", "https://nova.your-company.example")
    api_key = os.environ["NOVA_OS_API_KEY"]

    async with Client(base_url=base_url, api_key=api_key) as c:
        # 1. Ingest the documents. The collection is created on first ingest.
        for doc in DOCS:
            await c.knowledge.ingest(
                content=doc["content"], title=doc["title"], collection=COLLECTION
            )
        print(f"Ingested {len(DOCS)} docs into '{COLLECTION}'.")

        # 2. A persona bound to the collection. knowledge_gate answers a confident
        #    hit on the cheap tier (~sub-second) and fails open to the planner on
        #    a miss. brain=true so a miss still gets the full pipeline.
        await c.employees.create(
            id="people-ops",
            display_name="People Ops",
            model_config={
                "answer": {"primary": "anthropic/claude-opus-4-7", "fallback": ["gemini/gemini-2.5-pro"]},
                "skill": {"primary": "gemini/gemini-2.5-flash"},
            },
        )
        await c.agents.create(
            id="handbook-copilot",
            type="persona",
            owner_employee="people-ops",
            brain=True,
            knowledge_bindings=[COLLECTION],
            knowledge_gate=True,
            description="Answers employee questions strictly from the company handbook, with citations.",
            instructions=(
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

        # 4. Cleanup for dev loops.
        await c.agents.delete("handbook-copilot")
        await c.employees.delete("people-ops")


if __name__ == "__main__":
    asyncio.run(main())
