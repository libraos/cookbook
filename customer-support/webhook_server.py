"""Customer support — partner-side webhook hosting the order-lookup tool.

Pairs with `support_agent.py`. Every time the agent calls the `order_lookup`
tool, Nova OS POSTs a signed JSON payload here. The HMAC-SHA256 signature is
verified by `WebhookRouter` before the handler runs.

In production: replace the in-memory `_ORDER_DB` with a real query against your
order-management system (Postgres, Shopify Admin API, your OMS, …). The handler
signature is unchanged.

Prerequisites::

    pip install nova-os-sdk fastapi uvicorn
    export NOVA_CB_SECRET=<copy from Nova OS dashboard or generate locally>

Run::

    uvicorn webhook_server:app --port 8080 --reload
"""

from __future__ import annotations

import os

from fastapi import FastAPI

try:
    from nova_os.callbacks import WebhookRouter
except ImportError:
    # Fallback so this file is syntax-checkable without the SDK installed.
    from fastapi import APIRouter

    class WebhookRouter:  # type: ignore[no-redef]
        def __init__(self, secret: str) -> None:
            self.secret = secret

        def tool(self, name: str):  # noqa: ANN202
            def decorator(fn):  # noqa: ANN202
                return fn
            return decorator

        def fastapi_router(self) -> APIRouter:
            return APIRouter()


# Toy in-memory order DB. Replace with your real OMS lookup.
_ORDER_DB: dict[str, dict] = {
    "ORD-5591": {
        "status": "in_transit",
        "carrier": "UPS",
        "tracking": "1Z999AA10123456784",
        "eta": "2026-07-04",
    },
    "ORD-5588": {
        "status": "delivered",
        "carrier": "FedEx",
        "tracking": "7749 1234 5678",
        "delivered_on": "2026-06-28",
    },
}


router = WebhookRouter(secret=os.environ.get("NOVA_CB_SECRET", "changeme"))


@router.tool("order_lookup")
async def order_lookup(input: dict, ctx: dict) -> dict:
    """Return the current status of an order by id.

    The agent relays these fields to the customer. Return a clear not-found
    shape rather than raising, so the agent can respond gracefully.
    """
    order_id = (input.get("order_id") or "").strip().upper()
    order = _ORDER_DB.get(order_id)
    if order is None:
        return {"order_id": order_id, "found": False}
    return {"order_id": order_id, "found": True, **order, "agent_id": ctx.get("agent_id")}


app = FastAPI(title="Customer-support order-lookup webhook")
app.include_router(router.fastapi_router(), prefix="/nova/cb")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
