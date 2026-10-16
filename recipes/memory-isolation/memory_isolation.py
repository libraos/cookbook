"""Observe recall with two real user identities and fresh conversations."""
from __future__ import annotations

import asyncio
import json
import os
from uuid import uuid4

import httpx
from libraos import Client


async def identity(http: httpx.AsyncClient) -> dict:
    response = await http.get("/oauth/userinfo")
    response.raise_for_status()
    user = response.json()
    roles = set(user.get("roles") or []) | {user.get("role")}
    if not user.get("sub") or "admin" in roles:
        raise ValueError("Use a normal user's token, not an admin or service identity")
    return user


async def recall(client: Client, agent: str, question: str, *, end_user: str | None = None, conversation_id: str | None = None) -> str:
    # A NEW conversation, with NO previous user or assistant turns supplied.
    reply = await client.messages.create(
        agent_id=agent,
        messages=[{"role": "user", "content": question}],
        metadata={"conversation_id": conversation_id or str(uuid4())},
        end_user=end_user,
    )
    return reply.text


async def conversation_boundary(a_http: httpx.AsyncClient, b_http: httpx.AsyncClient, conversation_id: str, a_id: str) -> None:
    """A positive read first, then B denial: a missing record cannot pass."""
    path = "/v1/conversations/" + conversation_id
    # Conversation persistence can lag behind the completed model response.
    for attempt in range(10):
        own = await a_http.get(path)
        if own.status_code != 404:
            break
        await asyncio.sleep(0.2)
    own.raise_for_status()
    if own.json().get("id") != conversation_id:
        raise ValueError("A's conversation read did not return the requested record")
    for headers in ({}, {"X-End-User": a_id, "X-Canonical-User": a_id}):
        other = await b_http.get(path, headers=headers)
        if other.status_code not in {403, 404}:
            other.raise_for_status()
            raise ValueError("B could read A's persisted conversation")


async def exercise(admin: Client, a: Client, b: Client, a_id: str, *, boundary_check=None) -> dict:
    agent = "cookbook-memory-" + uuid4().hex[:12]
    marker = "tea-" + uuid4().hex
    await admin.agents.create(
        name=agent, agent_type="persona", visibility="public", tool_scope="none",
        system="Remember the current user's preferences. Use only that user's memory. If unknown, say unknown.",
    )
    try:
        conversation_id = str(uuid4())
        await recall(a, agent, f"My preferred tea label is {marker}. Remember this preference.", conversation_id=conversation_id)
        if boundary_check is not None:
            await boundary_check(conversation_id)
        question = "What is my preferred tea label? Return the label exactly, or unknown if I never told you."
        a_reply = await recall(a, agent, question)
        b_reply = await recall(b, agent, question)
        # A normal caller must not gain another identity by supplying a header.
        spoof_reply = await recall(b, agent, question, end_user=a_id)
        return {
            "agent": agent, "marker": marker,
            "a_recalled": marker in a_reply,
            "b_isolated": marker not in b_reply,
            "b_override_isolated": marker not in spoof_reply,
            "conversation_access_checked": boundary_check is not None,
            "responses": {"a": a_reply, "b": b_reply, "b_with_override": spoof_reply},
        }
    finally:
        # Removing an agent does NOT promise deletion of its stored memory.
        await admin.agents.delete(agent)


async def run() -> dict:
    url = os.environ.get("LIBRA_OS_URL", "http://localhost:8900")
    a_token, b_token = os.environ["LIBRA_OS_USER_A_TOKEN"], os.environ["LIBRA_OS_USER_B_TOKEN"]
    users = []
    for token in (a_token, b_token):
        async with httpx.AsyncClient(base_url=url, headers={"Authorization": f"Bearer {token}"}) as http:
            users.append(await identity(http))
            response = await http.get("/v1/managed/memory", params={"agent_id": "cookbook-memory-preflight"})
            response.raise_for_status()
            if response.json().get("enabled") is not True:
                raise ValueError("Enable LIBRA_OS_OBSERVATIONAL_MEMORY=1 on the Runtime")
    if users[0]["sub"] == users[1]["sub"]:
        raise ValueError("A and B must be different authenticated users")
    if users[0].get("org_id") != users[1].get("org_id"):
        raise ValueError("Use two users in the same organization to test user isolation")
    async with (
        Client(base_url=url, api_key=os.environ["LIBRA_OS_API_KEY"], timeout=120) as admin,
        Client(base_url=url, api_key=a_token, timeout=120) as a,
        Client(base_url=url, api_key=b_token, timeout=120) as b,
        httpx.AsyncClient(base_url=url, headers={"Authorization": f"Bearer {a_token}"}) as a_http,
        httpx.AsyncClient(base_url=url, headers={"Authorization": f"Bearer {b_token}"}) as b_http,
    ):
        async def check(conversation_id):
            await conversation_boundary(a_http, b_http, conversation_id, users[0]["sub"])
        return await exercise(admin, a, b, users[0]["sub"], boundary_check=check)


if __name__ == "__main__":
    report = asyncio.run(run())
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if all(report[k] for k in ("a_recalled", "b_isolated", "b_override_isolated")) else 1)
