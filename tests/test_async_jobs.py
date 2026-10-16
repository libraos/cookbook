import json

import httpx
import pytest

from conftest import load_example

example = load_example("recipes/async-jobs/async_jobs.py")


def receipt(tmp_path):
    path = tmp_path / "receipt.json"
    data = {"version": 1, "base_url": "http://kernel", "agent": "demo", "message": "summarize", "idempotency_key": "stable-key"}
    example.save(path, data, new=True)
    return path, data


async def test_uncertain_submission_resumes_with_same_key_then_only_reads(tmp_path):
    path, data = receipt(tmp_path)
    requests = []
    def server(request):
        requests.append(request)
        if len(requests) == 1:
            raise httpx.ReadTimeout("accepted but reply lost", request=request)
        if request.method == "POST":
            assert request.url.path == "/agents/v1/demo/jobs"
            assert request.headers["Idempotency-Key"] == "stable-key"
            assert json.loads(request.content) == {"message": "summarize"}
            return httpx.Response(202, json={"job_id": "j1", "status": "queued"})
        return httpx.Response(200, json={"job_id": "j1", "status": "done", "result": "report"})
    async with httpx.AsyncClient(base_url="http://kernel", transport=httpx.MockTransport(server)) as http:
        with pytest.raises(httpx.ReadTimeout):
            await example.Jobs(http, data, path).ensure_submitted()
        resumed = example.Jobs(http, json.loads(path.read_text()), path)
        assert await resumed.ensure_submitted() == "j1"
        # A fresh instance represents another process after receipt persistence.
        again = example.Jobs(http, json.loads(path.read_text()), path)
        assert await again.ensure_submitted() == "j1"
        assert (await again.wait())["result"] == "report"
    assert [r.method for r in requests] == ["POST", "POST", "GET"]
    assert requests[0].headers["Idempotency-Key"] == requests[1].headers["Idempotency-Key"]
    assert "Authorization" not in path.read_text()


@pytest.mark.parametrize("terminal", ["done", "failed", "cancelled"])
async def test_terminal_states_are_preserved(tmp_path, terminal):
    path, data = receipt(tmp_path)
    data["job_id"] = "j1"
    states = iter(["queued", "running", terminal])
    async with httpx.AsyncClient(base_url="http://kernel", transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"job_id": "j1", "status": next(states)}))) as http:
        assert (await example.Jobs(http, data, path).wait(interval=0.001))["status"] == terminal


async def test_wait_timeout_keeps_receipt_and_never_cancels(tmp_path):
    path, data = receipt(tmp_path)
    data["job_id"] = "j1"
    calls = []
    def server(request):
        calls.append(request.method)
        return httpx.Response(200, json={"job_id": "j1", "status": "running"})
    async with httpx.AsyncClient(base_url="http://kernel", transport=httpx.MockTransport(server)) as http:
        with pytest.raises(TimeoutError):
            await example.Jobs(http, data, path).wait(timeout=0.01, interval=0.001)
    assert path.exists() and set(calls) == {"GET"}


@pytest.mark.parametrize("delete_status,final", [(200, "cancelled"), (409, "done")])
async def test_cancel_reads_actual_state_including_completion_race(tmp_path, delete_status, final):
    path, data = receipt(tmp_path)
    data["job_id"] = "j1"
    def server(request):
        return httpx.Response(delete_status if request.method == "DELETE" else 200, json={"job_id": "j1", "status": final})
    async with httpx.AsyncClient(base_url="http://kernel", transport=httpx.MockTransport(server)) as http:
        assert (await example.Jobs(http, data, path).cancel())["status"] == final


async def test_transient_read_failure_recovers(tmp_path):
    path, data = receipt(tmp_path)
    data["job_id"] = "j1"
    statuses = iter([503, 200])
    async with httpx.AsyncClient(base_url="http://kernel", transport=httpx.MockTransport(lambda r: httpx.Response(next(statuses), json={"job_id": "j1", "status": "done"}))) as http:
        assert (await example.Jobs(http, data, path).wait(interval=0.001))["status"] == "done"


@pytest.mark.parametrize("status", [401, 403, 404])
async def test_auth_and_missing_jobs_fail_without_retry(tmp_path, status):
    path, data = receipt(tmp_path)
    data["job_id"] = "j1"
    async with httpx.AsyncClient(base_url="http://kernel", transport=httpx.MockTransport(lambda r: httpx.Response(status))) as http:
        with pytest.raises(httpx.HTTPStatusError):
            await example.Jobs(http, data, path).wait()


def test_receipt_cannot_be_overwritten_or_reused_on_another_host(tmp_path):
    path, data = receipt(tmp_path)
    with pytest.raises(FileExistsError):
        example.save(path, data, new=True)
    with pytest.raises(ValueError, match="different Runtime"):
        example.Jobs(httpx.AsyncClient(base_url="http://another-kernel"), data, path)
