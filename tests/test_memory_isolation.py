import json

import httpx
import pytest
from libraos import Client

from conftest import load_example

example = load_example("recipes/memory-isolation/memory_isolation.py")


async def test_fresh_conversations_use_separate_authenticated_clients():
    seen = []
    def server(request):
        seen.append(request)
        return httpx.Response(200, json={"id": "m1", "type": "message", "role": "assistant", "content": [{"type": "text", "text": "unknown"}], "stop_reason": "end_turn", "usage": {"input_tokens": 1, "output_tokens": 1}})
    transport = httpx.MockTransport(server)
    async with Client(base_url="http://kernel", api_key="user-a", transport=transport) as a, Client(base_url="http://kernel", api_key="user-b", transport=transport) as b:
        await example.recall(a, "memory-agent", "remember tea")
        await example.recall(a, "memory-agent", "recall tea")
        await example.recall(b, "memory-agent", "recall tea", end_user="a-subject")
    bodies = [json.loads(r.content) for r in seen]
    assert [r.headers["Authorization"] for r in seen] == ["Bearer user-a", "Bearer user-a", "Bearer user-b"]
    assert len({b["metadata"]["conversation_id"] for b in bodies}) == 3
    assert all(len(b["messages"]) == 1 for b in bodies)
    assert "remember tea" not in seen[2].content.decode()
    assert seen[2].headers["X-End-User"] == "a-subject"
    # This tests wire construction, NOT the server's authorization decisions.


@pytest.mark.parametrize("user", [{"sub": "admin", "role": "admin"}, {"sub": "admin", "roles": ["admin"]}, {}])
async def test_invalid_identity_fails_preflight(user):
    async with httpx.AsyncClient(base_url="http://kernel", transport=httpx.MockTransport(lambda r: httpx.Response(200, json=user))) as http:
        with pytest.raises(ValueError):
            await example.identity(http)
