"""First agent in Python. See ../README.md for the local bearer token setup."""
from __future__ import annotations

import asyncio
import os

import httpx


async def run(http: httpx.AsyncClient) -> list[dict]:
    response = await http.post("/v1/agents", headers={"anthropic-beta": "managed-agents-2026-04-01"}, json={
        "name": "first-assistant", "agent_type": "persona",
        "system": "You are a friendly assistant. Answer in two sentences or fewer.",
    })
    if response.status_code != 409:
        response.raise_for_status()
    messages, results = [], []
    conversation_id = None
    for question in ["My name is Sam. What can you help me with?", "What's my name?"]:
        messages.append({"role": "user", "content": question})
        response = await http.post("/agents/v1/first-assistant/chat", json={
            "messages": messages, "conversation_id": conversation_id,
        })
        response.raise_for_status()
        result = response.json()
        if not isinstance(result.get("response"), str) or not result.get("conversation_id"):
            raise ValueError("Expected response text and conversation_id")
        conversation_id = result["conversation_id"]
        messages.append({"role": "assistant", "content": result["response"]})
        results.append(result)
    return results


async def main() -> None:
    async with httpx.AsyncClient(
        base_url=os.environ.get("LIBRA_OS_URL", "http://localhost:8900"),
        headers={"Authorization": f"Bearer {os.environ['LIBRA_OS_API_KEY']}"}, timeout=120,
    ) as http:
        for result in await run(http):
            print(result["response"])


if __name__ == "__main__":
    asyncio.run(main())
