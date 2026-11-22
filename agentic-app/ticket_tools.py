from __future__ import annotations

import os
from typing import Any

import httpx


class TicketApi:
    def __init__(self) -> None:
        self.base_url = os.getenv("MAIN_APP_API_URL", "http://localhost:8081").rstrip("/")
        self.ca_file = os.getenv("MAIN_APP_CA_FILE") or True

    async def search(self, query: str, limit: int, access_token: str) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=10, verify=self.ca_file) as client:
            response = await client.post(
                "/api/internal/tickets/search",
                json={"query": query, "limit": min(max(limit, 1), 25)},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            return response.json()

    async def get(self, ticket_id: int, access_token: str) -> dict[str, Any] | None:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=10, verify=self.ca_file) as client:
            response = await client.get(
                f"/api/internal/tickets/{ticket_id}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
