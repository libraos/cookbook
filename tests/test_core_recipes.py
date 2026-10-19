"""Existing core recipes: actual SDK serialization against a simulated server.

These tests prove client contracts, not a real kernel's model/guardrail behavior.
"""
import json

import httpx
import jsonschema
import pytest
from libraos import Client
from libraos.errors import AuthenticationError, LibraOSError
from libraos.client import RetryConfig

from conftest import load_example

first = load_example("get-started/01-first-agent/first-agent.py")
tickets = load_example("recipes/ticket-routing/ticket_routing.py")
qa = load_example("recipes/document-qa/document_qa.py")


async def test_first_agent_preserves_conversation_history():
    calls = []
    def server(request):
        calls.append(json.loads(request.content))
        if request.url.path == "/v1/agents":
            return httpx.Response(201, json={"id": "first-assistant"})
        return httpx.Response(200, json={"content": [{"type": "text", "text": "Hello"}]})
    async with Client(base_url="http://kernel", api_key="test", transport=httpx.MockTransport(server)) as client:
        assert len(await first.run(client)) == 2
    assert calls[0]["tool_scope"] == "none"
    assert [m["role"] for m in calls[2]["messages"]] == ["user", "assistant", "user"]


@pytest.mark.parametrize("status,at_create", [(401, True), (403, True), (503, False)])
async def test_first_agent_credential_and_model_errors_propagate(status, at_create):
    def server(request):
        if not at_create and request.url.path == "/v1/agents":
            return httpx.Response(201, json={"id": "first-assistant"})
        return httpx.Response(status, json={"error": "unavailable"})
    async with Client(base_url="http://kernel", api_key="test", transport=httpx.MockTransport(server), retry_config=RetryConfig(max_attempts=1)) as client:
        with pytest.raises(LibraOSError) as caught:
            await first.run(client)
        assert caught.value.status == status


async def test_ticket_schema_rejects_invalid_and_missing_intent():
    for bad in [{"intent": "invented", "reasoning": "x"}, {"reasoning": "x"}]:
        async with httpx.AsyncClient(base_url="http://kernel", transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"output": bad}))) as http:
            with pytest.raises(jsonschema.ValidationError):
                await tickets.classify(http, "a ticket")
    async with httpx.AsyncClient(base_url="http://kernel", transport=httpx.MockTransport(lambda r: httpx.Response(422, json={"error": "output_violation"}))) as http:
        with pytest.raises(httpx.HTTPStatusError):
            await tickets.classify(http, "a ticket")


async def test_ticket_wrong_classification_is_counted_separately_from_schema(monkeypatch):
    monkeypatch.setenv("LIBRA_OS_API_KEY", "test-only")
    monkeypatch.setattr(tickets, "load_labelled", lambda: [{"ticket": "Cannot sign in", "expected": "Account management"}])
    def server(request):
        if request.url.path == "/agents/v1/ticket-router/chat":
            return httpx.Response(200, json={"output": {"intent": "Feedback", "reasoning": "deliberately wrong fixture"}})
        return httpx.Response(200, json={})
    http_client = httpx.AsyncClient
    monkeypatch.setattr(tickets.httpx, "AsyncClient", lambda **kw: http_client(**{**kw, "transport": httpx.MockTransport(server)}))
    result = await tickets.main()
    assert result == {"correct": 0, "total": 1}


async def test_document_qa_binds_ingested_docs_and_exercises_a_miss(monkeypatch):
    monkeypatch.setenv("LIBRA_OS_API_KEY", "test-only")
    requests = []
    def server(request):
        requests.append(request)
        if request.url.path == "/v1/messages":
            return httpx.Response(200, json={"content": [{"type": "text", "text": "fixture answer"}]})
        return httpx.Response(200, json={})
    monkeypatch.setattr(qa, "Client", lambda **kw: Client(**kw, transport=httpx.MockTransport(server)))
    http_client = httpx.AsyncClient
    monkeypatch.setattr(qa.httpx, "AsyncClient", lambda **kw: http_client(**{**kw, "transport": httpx.MockTransport(server)}))
    await qa.main()
    # The collection is created (registered) before ingest, so the binding holds.
    order = [(r.method, r.url.path) for r in requests]
    create = order.index(("POST", "/api/knowledge/collections"))
    assert order.index(("DELETE", f"/api/knowledge/collections/{qa.COLLECTION}")) < create < order.index(("POST", "/v1/managed/knowledge/ingest"))
    assert not any(r.method == "DELETE" and r.url.path == "/v1/agents/handbook-copilot" for r in requests[create:])
    agent = next(json.loads(r.content) for r in requests if r.method == "POST" and r.url.path == "/v1/agents")
    assert agent["knowledge_bindings"] == [qa.COLLECTION]
    assert "never guess" in agent["system"]
    messages = [json.loads(r.content) for r in requests if r.url.path == "/v1/messages"]
    assert len(messages) == 3
    assert "parental leave" in messages[-1]["messages"][0]["content"]


async def test_document_qa_does_not_convert_runtime_failure_to_an_answer():
    async with Client(base_url="http://kernel", api_key="test-only", transport=httpx.MockTransport(lambda r: httpx.Response(401, json={"error": "invalid token"}))) as client:
        with pytest.raises(AuthenticationError):
            await qa.ask(client, "A policy question")
