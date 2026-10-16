"""Existing core recipes: actual SDK serialization against a simulated server.

These tests prove client contracts, not a real kernel's model/guardrail behavior.
"""
import json

import httpx
import jsonschema
import pytest
from libraos import Client
from libraos.errors import AuthenticationError

from conftest import load_example

first = load_example("get-started/01-first-agent/first_agent.py")
tickets = load_example("recipes/ticket-routing/ticket_routing.py")
qa = load_example("recipes/document-qa/document_qa.py")


async def test_first_agent_preserves_conversation_history():
    calls = []
    def server(request):
        calls.append(json.loads(request.content))
        if request.url.path == "/v1/agents":
            return httpx.Response(201, json={"id": "first-assistant"})
        return httpx.Response(200, json={"response": "Hello", "conversation_id": "c1"})
    async with httpx.AsyncClient(base_url="http://kernel", transport=httpx.MockTransport(server)) as http:
        assert len(await first.run(http)) == 2
    assert calls[2]["conversation_id"] == "c1"
    assert [m["role"] for m in calls[2]["messages"]] == ["user", "assistant", "user"]


@pytest.mark.parametrize("status,at_create", [(401, True), (403, True), (503, False)])
async def test_first_agent_credential_and_model_errors_propagate(status, at_create):
    def server(request):
        if not at_create and request.url.path == "/v1/agents":
            return httpx.Response(201, json={"id": "first-assistant"})
        return httpx.Response(status, json={"error": "unavailable"})
    async with httpx.AsyncClient(base_url="http://kernel", transport=httpx.MockTransport(server)) as http:
        with pytest.raises(httpx.HTTPStatusError):
            await first.run(http)


def test_ticket_schema_rejects_invalid_and_missing_intent():
    for bad in [{"intent": "invented", "reasoning": "x"}, {"reasoning": "x"}]:
        with pytest.raises(jsonschema.ValidationError):
            tickets.parse_verdict(json.dumps(bad))
    with pytest.raises(json.JSONDecodeError):
        tickets.parse_verdict("not JSON")


async def test_ticket_wrong_classification_is_counted_separately_from_schema(monkeypatch):
    monkeypatch.setenv("LIBRA_OS_API_KEY", "test-only")
    monkeypatch.setattr(tickets, "load_labelled", lambda: [{"ticket": "Cannot sign in", "expected": "Account management"}])
    def server(request):
        if request.url.path == "/v1/messages":
            return httpx.Response(200, json={"content": [{"type": "text", "text": '{"intent":"Feedback","reasoning":"deliberately wrong fixture"}'}]})
        return httpx.Response(200, json={})
    monkeypatch.setattr(tickets, "Client", lambda **kw: Client(**kw, transport=httpx.MockTransport(server)))
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
    await qa.main()
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
