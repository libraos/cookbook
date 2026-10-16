# Create an agent on your local LibraOS kernel and hold a short conversation,
# with the LibraOS Python SDK.  Python 3.10+:
#   pip install libraos-sdk
#   python first-agent.py
import asyncio
import os
from pathlib import Path

import httpx
from libraos import Client

# The kernel's settings, from get-started/.env (see ../README.md).
env = dict(
    line.split("=", 1)
    for line in (Path(__file__).parent / "../.env").read_text().splitlines()
    if line and not line.startswith("#") and "=" in line
)
URL = os.environ.get("LIBRA_OS_URL") or "http://localhost:" + (
    os.environ.get("LIBRAOS_PORT") or env.get("LIBRAOS_PORT") or "8900"
)
SECRET = env["LIBRA_OS_SERVICE_CLIENTS"].split("=", 1)[1]  # quickstart:admin=<secret>


async def main() -> None:
    # 1. A bearer token for the laptop-only quickstart client. The SDK takes a
    #    token; this one call fetches it from the kernel.
    res = httpx.post(
        f"{URL}/oauth/token",
        json={"grant_type": "client_credentials", "client_id": "quickstart", "client_secret": SECRET},
    )
    if res.status_code != 200:
        raise SystemExit(f"token: {res.status_code} {res.text}")
    token = res.json()["access_token"]

    async with Client(base_url=URL, api_key=token) as c:
        # 2. A persona agent. Re-running the script is safe. tool_scope "none":
        #    it only talks, so the kernel offers it no tools (and logs no warning).
        await c.agents.create(
            name="first-assistant",
            agent_type="persona",
            tool_scope="none",
            system="You are a friendly assistant. Answer in two sentences or fewer.",
        )
        print("create agent: ok")

        # 3. Two turns. The kernel does not replay history for you: send the
        #    whole conversation every turn.
        messages: list[dict] = []
        for question in ["My name is Sam. What can you help me with?", "What's my name?"]:
            messages.append({"role": "user", "content": question})
            reply = await c.messages.create("first-assistant", messages)
            messages.append({"role": "assistant", "content": reply.text})
            print(f"\nyou:   {question}\nagent: {reply.text}")


asyncio.run(main())
