from __future__ import annotations

import asyncio
from typing import Any

from mcp import Client
from mcp.server import MCPServer

from auth import Principal, current_principal, principal_context
from rag import RagService
from ticket_tools import TicketApi


mcp_server = MCPServer("service-desk-agentic")
ticket_api = TicketApi()
rag_service: RagService | None = None


def set_rag_service(service: RagService) -> None:
    global rag_service
    rag_service = service


@mcp_server.tool()
async def search_tickets(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Search tickets visible to the authenticated user."""
    principal = current_principal()
    return await ticket_api.search(query, limit, principal.access_token)


@mcp_server.tool()
async def get_ticket(ticket_id: int) -> dict[str, Any] | None:
    """Read one ticket if the authenticated user is allowed to see it."""
    principal = current_principal()
    return await ticket_api.get(ticket_id, principal.access_token)


@mcp_server.tool()
async def search_knowledge(query: str, limit: int = 5, language: str | None = None) -> list[dict[str, Any]]:
    """Search the approved knowledge base and return source citations."""
    current_principal()
    if rag_service is None:
        raise RuntimeError("The knowledge base is not initialized.")
    hits = await asyncio.to_thread(rag_service.search, query, limit, language)
    return [
        {"text": hit.text, "score": hit.score, "citation": hit.citation(), "language": hit.language}
        for hit in hits
    ]


async def call_as_user(principal: Principal, name: str, arguments: dict[str, Any]) -> Any:
    with principal_context(principal):
        async with Client(mcp_server) as client:
            result = await client.call_tool(name, arguments)
    if result.is_error:
        detail = "\n".join(item.text for item in result.content if hasattr(item, "text"))
        raise RuntimeError(f"MCP tool '{name}' failed: {detail}")
    if result.structured_content is not None:
        structured = result.structured_content
        if isinstance(structured, dict) and set(structured) == {"result"}:
            return structured["result"]
        return structured
    return [item.text for item in result.content if hasattr(item, "text")]
