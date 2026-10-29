import hashlib
import hmac
import json
import time

import httpx
import pytest

from conftest import load_example

webhook = load_example("recipes/tool-calling/webhook_server.py")
example = load_example("recipes/tool-calling/tool_calling.py")


def signed(payload, key="call-1", secret="test-only-secret"):
    body = json.dumps(payload).encode()
    ts = int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.{key}.".encode() + body, hashlib.sha256).hexdigest()
    return body, {"X-LibraOS-Signature": f"t={ts},v1={sig}", "X-LibraOS-Idempotency-Key": key}


@pytest.mark.parametrize("order_id,found", [("ORD-5591", True), ("ORD-missing", False)])
async def test_signed_callback_and_duplicate_delivery(tmp_path, order_id, found):
    receipts = tmp_path / "receipts.jsonl"
    app = webhook.create_app("test-only-secret", receipts)
    body, headers = signed({"name": "order_lookup", "tool_use_id": "call-1", "input": {"order_id": order_id}})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://callback") as http:
        first = await http.post("/callback/", content=body, headers=headers)
        second = await http.post("/callback/", content=body, headers=headers)
    assert first.status_code == 200
    assert first.json() == second.json()
    assert first.json()["is_error"] is False
    assert json.loads(first.json()["output"])["found"] is found
    assert len(receipts.read_text().splitlines()) == 1


async def test_invalid_signature_never_executes_handler(tmp_path):
    receipts = tmp_path / "receipts.jsonl"
    body, headers = signed({"name": "order_lookup", "input": {"order_id": "ORD-5591"}}, secret="wrong")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=webhook.create_app("test-only-secret", receipts)), base_url="http://callback") as http:
        result = await http.post("/callback/", content=body, headers=headers)
    assert result.status_code == 401
    assert not receipts.exists()


async def test_registration_forces_the_lookup_and_keeps_the_secret_out():
    sent = []

    def kernel(request):
        sent.append(request)
        return httpx.Response(404 if request.method == "DELETE" else 200, json={})
    async with httpx.AsyncClient(transport=httpx.MockTransport(kernel), base_url="http://kernel") as http:
        await example.register(http)
    assert [(r.method, r.url.path) for r in sent] == [
        ("DELETE", "/v1/agents/cookbook-order-lookup"), ("POST", "/v1/agents")]
    agent = json.loads(sent[1].content)
    assert agent["tool_choice"] == "order_lookup" and agent["tool_scope"] == "none"
    assert "output_type" not in agent
    callback = agent["custom_tools"][0]["callback"]
    assert callback["auth"] == {"type": "hmac_sha256", "secret_ref": "LIBRA_OS_CALLBACK_SECRET_COOKBOOK"}
    assert callback["url"].endswith("/callback/")


def answering(text, seen=None):
    def kernel(request):
        if seen is not None:
            seen.append(json.loads(request.content))
        return httpx.Response(200, json={"response": text})
    return httpx.MockTransport(kernel)


@pytest.mark.parametrize("text", [
    '{"order_id": "ORD-5591", "status": "in_transit"}',
    '```json\n{"order_id": "ORD-5591", "status": "in_transit"}\n```',
])
async def test_typed_answer_without_memory(text):
    seen = []
    async with httpx.AsyncClient(transport=answering(text, seen), base_url="http://kernel") as http:
        result = await example.ask(http, "ORD-5591")
    assert result["structured"] == {"order_id": "ORD-5591", "status": "in_transit"}
    assert seen[0]["no_memory"] is True


@pytest.mark.parametrize("text", [
    "Order ORD-5591 is in transit with UPS.",
    '{"order_id": "ORD-5591\\u201c", "status": "in_transit"}',
    '{"order_id": "ORD-5591", "status": "delivered"}',
    '{"order_id": "ORD-5591", "found": false}',
    '{"order_id": "ORD-5591", "status": "in_transit", "carrier": "UPS"}',
])
async def test_answer_outside_the_contract_is_an_error(text):
    async with httpx.AsyncClient(transport=answering(text), base_url="http://kernel") as http:
        with pytest.raises(ValueError):
            await example.ask(http, "ORD-5591")


@pytest.mark.parametrize("status", [401, 403, 502, 503])
async def test_runtime_errors_do_not_become_successful_orders(status):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(status, json={"error": "unavailable"})), base_url="http://kernel") as http:
        with pytest.raises(httpx.HTTPStatusError):
            await example.ask(http, "ORD-5591")


async def test_disconnected_runtime_is_not_a_not_found_order():
    def fail(request):
        raise httpx.ConnectError("offline", request=request)
    async with httpx.AsyncClient(transport=httpx.MockTransport(fail), base_url="http://kernel") as http:
        with pytest.raises(httpx.ConnectError):
            await example.ask(http, "ORD-5591")
