"""A signed, read-only order lookup. Run: python webhook_server.py."""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI
from libraos.callbacks import WebhookRouter

ORDERS = {"ORD-5591": {"status": "in_transit", "carrier": "UPS"}}


def create_app(secret: str, receipts: Path | None = None) -> FastAPI:
    router = WebhookRouter(secret=secret)

    @router.tool("order_lookup")
    async def lookup(data: dict, ctx: dict) -> str:
        order_id = data.get("order_id")
        if not isinstance(order_id, str) or not order_id.strip():
            raise ValueError("order_id must be a non-empty string")
        order_id = order_id.strip().upper()
        order = ORDERS.get(order_id)
        result = {"order_id": order_id, "found": order is not None, **(order or {})}
        # Local evidence that a signed callback actually reached the handler.
        # No credentials or customer text are recorded. Single-process demo only.
        if receipts is not None:
            with receipts.open("a", encoding="utf-8") as out:
                out.write(json.dumps({"tool_use_id": ctx["tool_use_id"], **result}) + "\n")
        return json.dumps(result)  # The callback protocol's output is a string.

    app = FastAPI(title="Cookbook order lookup")
    app.include_router(router.fastapi_router(), prefix="/callback")
    return app


if __name__ == "__main__":
    import uvicorn

    # The kernel container reaches this host as host.docker.internal. On Linux
    # that is the Docker bridge address, so the default listens on every
    # interface; set COOKBOOK_WEBHOOK_HOST=172.17.0.1 (your bridge) to narrow
    # it. A different port must match compose.yaml and the agent's callback.url.
    uvicorn.run(
        create_app(os.environ["LIBRA_OS_CALLBACK_SECRET_COOKBOOK"], Path("receipts.jsonl")),
        host=os.environ.get("COOKBOOK_WEBHOOK_HOST", "0.0.0.0"),
        port=int(os.environ.get("COOKBOOK_WEBHOOK_PORT", "8080")),
    )
