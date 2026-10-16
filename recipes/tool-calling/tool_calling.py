"""Call the mounted tool agent; errors remain errors, never invented orders."""
from __future__ import annotations

import argparse
import asyncio
import json
import os

import httpx

CHAT_PATH = "/v1/apps/cookbook-tools/agents/cookbook-order-lookup/chat"


async def ask(http: httpx.AsyncClient, order_id: str) -> dict:
    response = await http.post(CHAT_PATH, json={
        "messages": [{"role": "user", "content": f"Look up order {order_id}. Use order_lookup."}],
        "stream": False,
    })
    response.raise_for_status()
    result = response.json()
    if not isinstance(result.get("response"), str):
        raise ValueError("Runtime did not return a chat response")
    structured = json.loads(result["response"])
    if not isinstance(structured, dict) or structured.get("order_id") != order_id or structured.get("status") not in {"in_transit", "not_found", "unavailable"}:
        raise ValueError("Order response violates the example's output contract")
    result["structured"] = structured
    return result


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("order_id", nargs="?", default="ORD-5591")
    args = parser.parse_args()
    async with httpx.AsyncClient(
        base_url=os.environ.get("LIBRA_OS_URL", "http://localhost:8900"),
        headers={"Authorization": f"Bearer {os.environ['LIBRA_OS_API_KEY']}"},
        timeout=120,
    ) as http:
        print(json.dumps(await ask(http, args.order_id), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
