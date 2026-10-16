# Create an agent on your local LibraOS kernel and hold a short conversation,
# with the LibraOS Python SDK.  Python 3.10+:
#   pip install libraos-sdk
#   python first-agent.py
import asyncio
import os
from pathlib import Path

import httpx
from libraos import Client

async def run(c: Client) -> list[str]:
    """Create an agent and run two turns; testable without loading credentials."""
    await c.agents.create(
        name="first-assistant", agent_type="persona", tool_scope="none",
        system="You are a friendly assistant. Answer in two sentences or fewer.",
    )
    print("create agent: ok")
    messages, replies = [], []
    for question in ["My name is Sam. What can you help me with?", "What's my name?"]:
        messages.append({"role": "user", "content": question})
        reply = await c.messages.create("first-assistant", messages)
        if not reply.text:
            raise ValueError("Expected a non-empty assistant reply")
        messages.append({"role": "assistant", "content": reply.text})
        replies.append(reply.text)
        print(f"\nyou:   {question}\nagent: {reply.text}")
    return replies


async def main() -> None:
    # Read configuration only when executing, never merely importing the example.
    env_path = Path(__file__).parent / "../.env"
    env = dict(
        line.split("=", 1) for line in env_path.read_text().splitlines()
        if line and not line.startswith("#") and "=" in line
    ) if env_path.exists() else {}
    url = os.environ.get("LIBRA_OS_URL") or "http://localhost:" + (
        os.environ.get("LIBRAOS_PORT") or env.get("LIBRAOS_PORT") or "8900"
    )
    # 1. A bearer token for the laptop-only quickstart client. The SDK takes a
    #    token; this one call fetches it from the kernel.
    token = os.environ.get("LIBRA_OS_API_KEY")
    if not token:
        secret = env["LIBRA_OS_SERVICE_CLIENTS"].split("=", 1)[1]
        async with httpx.AsyncClient() as http:
            res = await http.post(f"{url}/oauth/token", json={
                "grant_type": "client_credentials", "client_id": "quickstart", "client_secret": secret,
            })
            res.raise_for_status()
            token = res.json()["access_token"]
    async with Client(base_url=url, api_key=token, timeout=120) as c:
        await run(c)


if __name__ == "__main__":
    asyncio.run(main())
