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
    """Create the agent, or replace an earlier definition of it."""
    response = await http.post("/v1/agents", json=AGENT)
    # Before v0.3.0 this endpoint was beta-gated (426), and with the beta header
    # it answered 200 while dropping custom_tools; the forced tool_choice was
    # then skipped and the model answered with no tool.
    if response.status_code == 426:
        raise RuntimeError("POST /v1/agents answered 426: this recipe requires kernel v0.3.0 or later")
    response.raise_for_status()
    if "order_lookup" not in {t.get("name") for t in response.json().get("custom_tools") or []}:
        raise RuntimeError("The Runtime did not keep order_lookup; this recipe requires kernel v0.3.0 or later")


def parse_answer(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):  # Some models fence JSON despite the instruction.
        body, _, tail = text.split("\n", 1)[-1].rpartition("```")
        if tail.strip():
            raise ValueError("Text after the JSON answer")
        text = body
    return json.loads(text)


def tool_outcome(content: str) -> str:
    """The status a recorded order_lookup result supports."""
    if content.startswith("error:"):  # The Runtime could not deliver the callback.
        return "unavailable"
    # A delivered result arrives fenced as untrusted data around {"output", "is_error"}.
    envelope, _ = json.JSONDecoder().raw_decode(content, content.index("{"))
    if envelope.get("is_error"):
        return "unavailable"
    return "in_transit" if json.loads(envelope["output"])["found"] else "not_found"


def looked_up(call: dict) -> str | None:
    """The order_id an order_lookup call asked for, or None for any other or malformed call."""
    function = call.get("function") or {}
    if function.get("name") != "order_lookup":
        return None
    try:
        return json.loads(function.get("arguments") or "").get("order_id")
    except (ValueError, AttributeError):
        return None


def recorded_status(transcript: list, order_id: str) -> str:
    """The outcome of the last order_lookup the Runtime ran for exactly this order_id."""
    calls = {call.get("id") for message in transcript if message.get("role") == "assistant"
             for call in message.get("tool_calls") or [] if looked_up(call) == order_id}
    results = [m.get("content") or "" for m in transcript
               if m.get("role") == "tool" and m.get("tool_call_id") in calls]
    if not results:
        raise ValueError(f"No order_lookup ran for {order_id}; the answer is not evidence")
    try:
        return tool_outcome(results[-1])
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError("Unreadable order_lookup result") from exc


async def ask(http: httpx.AsyncClient, order_id: str) -> dict:
    response = await http.post(f"/agents/v1/{AGENT_ID}/chat", json={
        "message": f"Look up order {order_id}.",
        # A lookup is stateless. Recalled answers from earlier turns carry no tool
        # results, and the model would repeat them instead of calling the tool.
        "no_memory": True,
        # Returns tool_transcript: the calls the Runtime made and their results.
        "include_metadata": True,
    })
    response.raise_for_status()
    result = response.json()
    if not isinstance(result.get("response"), str):
        raise ValueError("Runtime did not return a chat response")
    structured = parse_answer(result["response"])
    if not isinstance(structured, dict) or set(structured) != {"order_id", "status"} \
            or structured["order_id"] != order_id or not isinstance(structured["status"], str) \
            or structured["status"] not in STATUSES:
        raise ValueError("Order response violates the example's output contract")
    # The answer must restate what the tool returned for this exact order_id. A
    # malformed argument such as "ORD-5591," reaches the webhook as an unknown
    # order, so a relayed not_found would otherwise look valid.
    if structured["status"] != recorded_status(result.get("tool_transcript") or [], order_id):
        raise ValueError("The answer does not match the recorded order_lookup result")
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
