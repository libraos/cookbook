"""Native HTTP jobs: submit once, persist a receipt, resume or cancel later."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

import httpx

TERMINAL = {"done", "failed", "cancelled"}
STATUSES = TERMINAL | {"queued", "running"}


def save(path: Path, receipt: dict, *, new: bool = False) -> None:
    if new:
        # Never overwrite the recovery handle for a previous run.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as out:
            json.dump(receipt, out, indent=2)
            out.flush()
            os.fsync(out.fileno())
    else:
        temp = path.with_name(path.name + "." + uuid4().hex + ".tmp")
        try:
            fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as out:
                json.dump(receipt, out, indent=2)
                out.flush()
                os.fsync(out.fileno())
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)


class Jobs:
    def __init__(self, http: httpx.AsyncClient, receipt: dict, path: Path):
        self.http, self.receipt, self.path = http, receipt, path
        if str(http.base_url).rstrip("/") != receipt["base_url"].rstrip("/"):
            raise ValueError("Receipt belongs to a different Runtime URL")
        self.route = "/agents/v1/" + quote(receipt["agent"], safe="") + "/jobs"

    async def ensure_submitted(self) -> str:
        if self.receipt.get("job_id"):
            return self.receipt["job_id"]
        response = await self.http.post(
            self.route, json={"message": self.receipt["message"]},
            headers={"Idempotency-Key": self.receipt["idempotency_key"]},
        )
        response.raise_for_status()
        job_id = response.json().get("job_id")
        if not isinstance(job_id, str) or not job_id:
            raise ValueError("Submission did not return a job_id")
        self.receipt["job_id"] = job_id
        save(self.path, self.receipt)
        return job_id

    async def get(self, *, timeout: float = 30) -> dict:
        job_id = self.receipt["job_id"]
        response = await self.http.get(self.route + "/" + quote(job_id, safe=""), timeout=timeout)
        response.raise_for_status()
        job = response.json()
        if job.get("job_id") != job_id or job.get("status") not in STATUSES:
            raise ValueError("Unexpected native job response; check Runtime/API compatibility")
        return job

    async def wait(self, timeout: float = 120, interval: float = 2) -> dict:
        if timeout <= 0 or interval <= 0:
            raise ValueError("timeout and interval must be positive")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                job = await self.get(timeout=min(30, max(0.001, deadline - time.monotonic())))
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code not in {429, 502, 503, 504}:
                    raise
                # Only reads are retried automatically. The receipt survives.
            else:
                if job["status"] in TERMINAL:
                    return job
            await asyncio.sleep(min(interval, max(0, deadline - time.monotonic())))
        raise TimeoutError("Local wait expired; job is NOT cancelled. Resume with the same receipt.")

    async def cancel(self) -> dict:
        job_id = self.receipt["job_id"]
        response = await self.http.delete(self.route + "/" + quote(job_id, safe=""))
        # Completion can win the race with cancellation. Return actual state.
        if response.status_code != 409:
            response.raise_for_status()
        return await self.get()


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["submit", "resume", "status", "cancel"])
    parser.add_argument("--receipt", type=Path, default=Path("job-receipt.json"))
    parser.add_argument("--agent", default="first-assistant")
    parser.add_argument("--message", default="Write a short checklist for reviewing a project handover.")
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args()
    url = os.environ.get("LIBRA_OS_URL", "http://localhost:8900").rstrip("/")
    # Validate credentials before creating a new local receipt.
    token = os.environ["LIBRA_OS_API_KEY"]
    if args.action == "submit":
        receipt = {"version": 1, "base_url": url, "agent": args.agent,
                   "message": args.message, "idempotency_key": uuid4().hex}
        save(args.receipt, receipt, new=True)  # BEFORE POST: recover an uncertain submission.
    else:
        receipt = json.loads(args.receipt.read_text())
        if receipt.get("version") != 1:
            raise ValueError("Unsupported receipt version")
    async with httpx.AsyncClient(base_url=url, headers={"Authorization": f"Bearer {token}"}, timeout=30) as http:
        jobs = Jobs(http, receipt, args.receipt)
        if args.action in {"status", "cancel"} and not receipt.get("job_id"):
            raise ValueError("Submission outcome unknown. Resume first using the saved idempotency key.")
        if args.action in {"submit", "resume"}:
            print(json.dumps({"job_id": await jobs.ensure_submitted(), "receipt": str(args.receipt)}))
        if args.action == "submit":
            return 0
        if args.action == "cancel":
            job = await jobs.cancel()
        elif args.action == "status":
            job = await jobs.get()
        else:
            job = await jobs.wait(args.timeout)
        print(json.dumps(job, indent=2))
        if args.action == "cancel" and job["status"] not in TERMINAL:
            print("Cancellation has not reached a terminal state; keep the receipt and query again.")
            return 3
        return {"failed": 1, "cancelled": 2}.get(job["status"], 0)


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except (httpx.HTTPError, TimeoutError, ValueError, OSError, KeyError) as exc:
        print(f"{type(exc).__name__}: {exc}")
        raise SystemExit(1)
