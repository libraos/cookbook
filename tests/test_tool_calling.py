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
