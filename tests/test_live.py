"""Opt-in behavioral evaluations. Never require a model's exact prose."""
import json
import os
from pathlib import Path

import httpx
import pytest

from conftest import load_example

pytestmark = pytest.mark.live


async def test_live_memory_recall_and_isolation():
    example = load_example("recipes/memory-isolation/memory_isolation.py")
    report = await example.run()
    assert report["conversation_access_checked"]
    assert report["a_recalled"], "A's unique preference was not recalled; inspect model/Runtime memory behavior"
    assert report["b_isolated"], "B received A's unique preference"
    assert report["b_override_isolated"], "B received A's preference after an identity override attempt"


async def test_live_tool_lookup_requires_callback_evidence():
    example = load_example("recipes/tool-calling/tool_calling.py")
    receipts = Path(os.environ["COOKBOOK_TOOL_RECEIPTS"])
    before = len(receipts.read_text().splitlines()) if receipts.exists() else 0
    async with httpx.AsyncClient(
        base_url=os.environ["LIBRA_OS_URL"], timeout=120,
        headers={"Authorization": f"Bearer {os.environ['LIBRA_OS_API_KEY']}"},
    ) as http:
        await example.register(http)
        known = await example.ask(http, "ORD-5591")
        missing = await example.ask(http, "ORD-NOT-FOUND")
    assert known["structured"]["status"] == "in_transit"
    assert missing["structured"]["status"] == "not_found"
    events = [json.loads(line) for line in receipts.read_text().splitlines()[before:]]
    assert any(e["order_id"] == "ORD-5591" and e["found"] for e in events)
    assert any(e["order_id"] == "ORD-NOT-FOUND" and not e["found"] for e in events)


async def test_live_webhook_unavailable():
    if os.environ.get("COOKBOOK_WEBHOOK_UNAVAILABLE") != "1":
        pytest.skip("Stop the demo webhook, then explicitly set COOKBOOK_WEBHOOK_UNAVAILABLE=1")
    example = load_example("recipes/tool-calling/tool_calling.py")
    async with httpx.AsyncClient(base_url=os.environ["LIBRA_OS_URL"], timeout=120, headers={"Authorization": f"Bearer {os.environ['LIBRA_OS_API_KEY']}"}) as http:
        await example.register(http)
        try:
            result = await example.ask(http, "ORD-5591")
        except httpx.HTTPStatusError as exc:
            # An upstream/tool failure is valid. Auth/setup errors are not proof.
            assert exc.response.status_code in {502, 503, 504}
        else:
            assert result["structured"]["status"] == "unavailable"


async def test_live_async_submit_and_resume(tmp_path):
    example = load_example("recipes/async-jobs/async_jobs.py")
    url = os.environ["LIBRA_OS_URL"].rstrip("/")
    from uuid import uuid4
    receipt = {"version": 1, "base_url": url, "agent": os.environ.get("COOKBOOK_JOB_AGENT", "first-assistant"), "message": "Return a short project handover checklist.", "idempotency_key": uuid4().hex}
    path = tmp_path / "receipt.json"
    example.save(path, receipt, new=True)
    async with httpx.AsyncClient(base_url=url, timeout=30, headers={"Authorization": f"Bearer {os.environ['LIBRA_OS_API_KEY']}"}) as http:
        first = example.Jobs(http, receipt, path)
        job_id = await first.ensure_submitted()
        resumed = example.Jobs(http, json.loads(path.read_text()), path)
        assert await resumed.ensure_submitted() == job_id
        result = await resumed.wait(timeout=180)
        assert result["status"] == "done", result
        assert isinstance(result.get("result"), str) and result["result"]
