"""Which memory each recipe reads, checked on the wire against a simulated server.

The get-started kernel keeps one observational-memory log per (canonical user,
agent). Stateless recipes opt out with no_memory; per-patient and per-customer
recipes select the log with X-Canonical-User, because X-End-User alone does not.
"""
import io
import json
import zipfile

import httpx
import pytest

from conftest import load_example

tickets = load_example("recipes/ticket-routing/ticket_routing.py")
moderation = load_example("recipes/content-moderation/content_moderation.py")
support = load_example("recipes/customer-support/support_agent.py")
triage = load_example("recipes/healthcare/clinical_note_triage.py")
legal = load_example("recipes/legaltech/contract_clause_extraction.py")


def recording(seen, reply):
    def server(request):
        seen.append(request)
        return reply(request)
    return httpx.MockTransport(server)


def route_all(monkeypatch, transport):
    """Every httpx.AsyncClient, the SDK's included, talks to the simulated server."""
    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: real(*a, **{**kw, "transport": transport}))


@pytest.mark.parametrize("call,path,output", [
    (lambda http: tickets.classify(http, "a ticket"), "/agents/v1/ticket-router/chat",
     {"intent": "Feedback", "reasoning": "fixture"}),
    (lambda http: moderation.moderate(http, "a post"), "/agents/v1/content-moderator/chat",
     {"verdict": "allow", "risk_score": 0.0, "categories": [], "reasoning": "fixture"}),
])
async def test_stateless_classifiers_neither_read_nor_write_memory(call, path, output):
    seen = []
    transport = recording(seen, lambda r: httpx.Response(200, json={"output": output}))
    async with httpx.AsyncClient(base_url="http://kernel", transport=transport) as http:
        await call(http)
    assert seen[0].url.path == path
    assert json.loads(seen[0].content)["no_memory"] is True


async def test_support_scopes_memory_per_customer_with_canonical_user():
    seen = []
    transport = recording(seen, lambda r: httpx.Response(200, json={"response": "fixture"}))
    async with httpx.AsyncClient(base_url="http://kernel", transport=transport) as http:
        await support.ask(http, "cust-1042", "Where is my order?")
    assert seen[0].headers["X-Canonical-User"] == "customer:cust-1042"
    assert "X-End-User" not in seen[0].headers


def bundled_agent(bundle: bytes, agent_id: str) -> str:
    with zipfile.ZipFile(io.BytesIO(bundle)) as z:
        return z.read(f"agents/{agent_id}.md").decode()


def frontmatter_fields(agent_file: str) -> dict:
    # The bundle writes one `key: <json>` line per field (JSON is valid YAML).
    head = agent_file.split("---\n")[1]
    return {k: json.loads(v) for k, v in (line.split(": ", 1) for line in head.splitlines())}


def test_support_agent_declares_the_pii_redactor():
    # Off by default from kernel v0.3.0; this agent handles customer text.
    fields = frontmatter_fields(bundled_agent(support.employee_bundle(), support.AGENT_ID))
    assert fields["guardrails"]["pii_redactor"] == "enabled"


async def test_triage_scopes_memory_per_patient_with_canonical_user(monkeypatch):
    monkeypatch.setenv("LIBRA_OS_API_KEY", "test-only")
    seen = []

    def reply(request):
        if request.url.path.endswith("/chat"):
            return httpx.Response(200, json={"output": {
                "patient_id": "PT-2026-0942", "urgency": "low", "suggested_action": "routine_followup",
                "red_flags": [], "rationale": "fixture"}})
        return httpx.Response(200, json={"id": "clinical-triage"})
    route_all(monkeypatch, recording(seen, reply))
    await triage.main()
    chat = next(r for r in seen if r.url.path == "/agents/v1/clinical-triage/chat")
    assert chat.headers["X-Canonical-User"] == "patient:PT-2026-0942"
    assert "X-End-User" not in chat.headers


async def test_contract_review_runs_without_memory_and_without_a_reload_nudge(monkeypatch):
    monkeypatch.setenv("LIBRA_OS_API_KEY", "test-only")
    seen = []

    def reply(request):
        if request.url.path.endswith("/chat"):
            return httpx.Response(200, json={"output": {"contract_id": "MSA-2026-042", "clauses": []}})
        return httpx.Response(200, json={"employee_id": legal.EMPLOYEE_ID, "agents_imported": 1})
    route_all(monkeypatch, recording(seen, reply))
    await legal.main()
    chat = next(r for r in seen if r.url.path == f"/agents/v1/{legal.AGENT_ID}/chat")
    assert json.loads(chat.content)["no_memory"] is True
    # Kernel v0.3.0 loads an imported bundle's agents itself (#1731).
    assert not any(r.method == "POST" and r.url.path == "/v1/agents" for r in seen)
