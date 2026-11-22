import asyncio
import time

import httpx
import jwt
from mcp import Client

from main import app
import mcp_tools
from auth import Principal
from mcp_tools import call_as_user, mcp_server
from ticket_tools import TicketApi


def test_mcp_server_exposes_only_read_tools() -> None:
    async def list_tools():
        async with Client(mcp_server) as client:
            return await client.list_tools()

    tools = asyncio.run(list_tools())

    assert {tool.name for tool in tools.tools} == {
        "get_ticket",
        "search_knowledge",
        "search_tickets",
    }


def test_internal_mcp_call_preserves_the_requesting_user(monkeypatch) -> None:
    received: dict[str, object] = {}

    async def fake_search(query: str, limit: int, access_token: str):
        received.update(query=query, limit=limit, access_token=access_token)
        return [{"id": 17, "title": "Visible ticket"}]

    monkeypatch.setattr(mcp_tools.ticket_api, "search", fake_search)
    principal = Principal("requester-1", frozenset({"Requester"}), "signed-user-token")

    result = asyncio.run(call_as_user(principal, "search_tickets", {"query": "VPN", "limit": 4}))

    assert result == [{"id": 17, "title": "Visible ticket"}]
    assert received == {"query": "VPN", "limit": 4, "access_token": "signed-user-token"}


def test_ticket_search_sends_free_text_in_the_body_not_the_url(monkeypatch) -> None:
    received: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        @staticmethod
        def json() -> list[dict[str, object]]:
            return []

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            received["base_url"] = kwargs["base_url"]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            return None

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            received.update(url=url, body=json, headers=headers)
            return FakeResponse()

    monkeypatch.setattr("ticket_tools.httpx.AsyncClient", FakeClient)
    monkeypatch.setenv("MAIN_APP_API_URL", "http://main-app:8081")

    result = asyncio.run(TicketApi().search("CONFIDENTIAL SEARCH TEXT", 4, "signed-user-token"))

    assert result == []
    assert received["url"] == "/api/internal/tickets/search"
    assert received["body"] == {"query": "CONFIDENTIAL SEARCH TEXT", "limit": 4}
    assert "CONFIDENTIAL SEARCH TEXT" not in str(received["url"])


def test_authenticated_streamable_http_mcp_endpoint_starts_and_lists_tools(monkeypatch, tmp_path) -> None:
    key = "test-signing-key-that-is-at-least-32-bytes"
    monkeypatch.setenv("AI_JWT_SIGNING_KEY", key)
    monkeypatch.setenv("QDRANT_URL", ":memory:")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SEED_DEMO_KB", "false")
    monkeypatch.setenv("PROMETHEUS_PORT", "0")
    token = jwt.encode(
        {
            "sub": "requester-1",
            "role": "Requester",
            "iss": "service-desk-main-app",
            "aud": "service-desk-agentic-app",
            "exp": int(time.time()) + 300,
        },
        key,
        algorithm="HS256",
    )

    async def list_remote_tools():
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="https://localhost:8000") as client:
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json, text/event-stream",
                }
                initialized = await client.post(
                    "/mcp",
                    headers=headers,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2025-11-25",
                            "capabilities": {},
                            "clientInfo": {"name": "integration-test", "version": "1.0"},
                        },
                    },
                )
                tools = await client.post(
                    "/mcp",
                    headers={**headers, "MCP-Protocol-Version": "2025-11-25"},
                    json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                )
                return initialized, tools

    initialized, tools = asyncio.run(list_remote_tools())

    assert initialized.status_code == 200
    assert tools.status_code == 200
    assert "serverInfo" in initialized.text
    assert "search_tickets" in tools.text
    assert "get_ticket" in tools.text
    assert "search_knowledge" in tools.text
