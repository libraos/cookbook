"""Register the order-lookup agent and ask it; errors remain errors, never invented orders."""
from __future__ import annotations

import argparse
import asyncio
import json
import os

import httpx

AGENT_ID = "cookbook-order-lookup"
STATUSES = {"in_transit", "not_found", "unavailable"}
# Resolved by the kernel container, not by this process. A remote Runtime needs
# your reachable HTTPS service here, plus its host policy and secret reference.
CALLBACK_URL = os.environ.get(
    "COOKBOOK_CALLBACK_URL",
    f"http://host.docker.internal:{os.environ.get('COOKBOOK_WEBHOOK_PORT', '8080')}/callback/",
)

# The JSON contract is asked for only after the tool has run. A schema imposed
# on the whole turn (output_type) also lands on the forced tool call and
# corrupts its arguments on OpenAI-compatible gateways; see the README.
SYSTEM = """\
You look up synthetic orders with the order_lookup tool and report what it returned.

Call order_lookup with the order_id exactly as the user wrote it. Relay only facts the tool returned; never guess a status. This tool reads synthetic data and cannot refund, cancel, or otherwise change an order.

After the tool has returned, your final reply is exactly one JSON object and nothing else, with two fields:
- "order_id": the order_id exactly as the user wrote it
- "status": "in_transit" when the tool returned the order, "not_found" when the tool returned found: false, "unavailable" when the tool call failed"""

AGENT = {
    "id": AGENT_ID,
    "name": AGENT_ID,
    "brain": False,
    # No catalog tools: the agent can call order_lookup and nothing else.
    "tool_scope": "none",
    # The first model call must be the lookup, so a status is never answered from the model alone.
    "tool_choice": "order_lookup",
    "system": SYSTEM,
    "custom_tools": [{
        "name": "order_lookup",
        "description": "Read the current status of an order by its order_id.",
        "input_schema": {
            "type": "object",
            "required": ["order_id"],
            "properties": {"order_id": {"type": "string"}},
            "additionalProperties": False,
        },
        "side_effects": False,
        "callback": {
            "url": CALLBACK_URL,
            # The kernel reads the secret from this env var; it never travels in the definition.
            "auth": {"type": "hmac_sha256", "secret_ref": "LIBRA_OS_CALLBACK_SECRET_COOKBOOK"},
            "timeout_sec": 5,
            "retry": {"max_attempts": 1, "backoff": "fixed"},
        },
    }],
}


async def register(http: httpx.AsyncClient) -> None:
    """Replace any earlier definition so re-runs pick up this file's version."""
    gone = await http.delete(f"/v1/agents/{AGENT_ID}")
    if gone.status_code != 404:
        gone.raise_for_status()
    (await http.post("/v1/agents", json=AGENT)).raise_for_status()


def parse_answer(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):  # Some models fence JSON despite the instruction.
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
    return json.loads(text)


async def ask(http: httpx.AsyncClient, order_id: str) -> dict:
    response = await http.post(f"/agents/v1/{AGENT_ID}/chat", json={
        "message": f"Look up order {order_id}.",
        # A lookup is stateless. Recalled answers from earlier turns carry no tool
        # results, and the model would repeat them instead of calling the tool.
        "no_memory": True,
    })
    response.raise_for_status()
    result = response.json()
    if not isinstance(result.get("response"), str):
        raise ValueError("Runtime did not return a chat response")
    structured = parse_answer(result["response"])
    if not isinstance(structured, dict) or set(structured) != {"order_id", "status"} \
            or structured["order_id"] != order_id or structured["status"] not in STATUSES:
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
        await register(http)
        print(json.dumps((await ask(http, args.order_id))["structured"], indent=2))


if __name__ == "__main__":
    asyncio.run(main())
