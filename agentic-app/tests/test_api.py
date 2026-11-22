import asyncio
from datetime import datetime, timedelta, timezone
import json
import logging
import os
from types import SimpleNamespace

from fastapi import HTTPException
import httpx
import jwt
from openai import APIStatusError

import main
from main import app
from telemetry import HTTP_REQUESTS


def test_health_endpoint_returns_ok() -> None:
    async def get_health() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="https://testserver",
        ) as client:
            return await client.get("/health")

    response = asyncio.run(get_health())

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_http_client_logs_do_not_include_request_urls() -> None:
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
    assert logging.getLogger("httpcore").getEffectiveLevel() >= logging.WARNING


def test_openai_errors_log_safe_diagnostics_without_request_content(monkeypatch, caplog) -> None:
    request_content = "private ticket description"
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    error = APIStatusError(
        "Upstream request failed.",
        response=httpx.Response(
            400,
            request=request,
            headers={"x-request-id": "req_test"},
            json={"code": "invalid_model", "param": "text.format", "type": "invalid_request_error"},
        ),
        body={"code": "invalid_model", "param": "text.format", "type": "invalid_request_error"},
    )

    class FakeResponses:
        async def create(self, **kwargs):
            raise error

    monkeypatch.setattr(main, "_openai_client", lambda: SimpleNamespace(responses=FakeResponses()))
    caplog.set_level(logging.ERROR, logger="main")

    try:
        asyncio.run(main._create_openai_response("ticket_copilot", input=request_content))
    except HTTPException as exc:
        assert exc.status_code == 502
        assert exc.detail == "The OpenAI request failed."
    else:
        raise AssertionError("Expected the OpenAI API error to become an HTTP 502.")

    assert "operation=ticket_copilot" in caplog.text
    assert "status_code=400" in caplog.text
    assert "error_code=invalid_model" in caplog.text
    assert "error_param=text.format" in caplog.text
    assert "request_id=req_test" in caplog.text
    assert request_content not in caplog.text


def _token(role: str = "Requester") -> str:
    key = "test-signing-key-that-is-at-least-32-bytes"
    os.environ["AI_JWT_SIGNING_KEY"] = key
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": "test-user",
            "role": role,
            "iss": "service-desk-main-app",
            "aud": "service-desk-agentic-app",
            "exp": now + timedelta(minutes=5),
        },
        key,
        algorithm="HS256",
    )


def test_ai_endpoints_require_a_valid_bearer_token() -> None:
    async def get_protected_endpoints() -> tuple[httpx.Response, httpx.Response]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
            rag = await client.post("/api/v1/rag/search", json={"query": "password"})
            help_response = await client.post("/api/v1/help", json={"question": "How do I reset a password?"})
            return rag, help_response

    rag, help_response = asyncio.run(get_protected_endpoints())

    assert rag.status_code == 401
    assert help_response.status_code == 401


def test_mcp_endpoint_requires_a_valid_bearer_token() -> None:
    async def get_mcp_endpoint() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="https://localhost") as client:
            return await client.get("/mcp")

    response = asyncio.run(get_mcp_endpoint())

    assert response.status_code == 401


def test_admin_document_api_rejects_non_admin_users() -> None:
    async def get_admin_endpoint() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
            return await client.get(
                "/api/v1/admin/documents",
                headers={"Authorization": f"Bearer {_token()}"},
            )

    response = asyncio.run(get_admin_endpoint())

    assert response.status_code == 403


def test_web_help_sends_only_the_question_to_openai(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class FakeResponses:
        async def create(self, **kwargs):
            calls.append(kwargs)
            annotation = SimpleNamespace(type="url_citation", title="Example source", url="https://example.test")
            content = SimpleNamespace(annotations=[annotation])
            message = SimpleNamespace(type="message", content=[content])
            return SimpleNamespace(output_text="A web answer.", output=[message])

    class FakeOpenAI:
        def __init__(self):
            self.responses = FakeResponses()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("WEB_SEARCH_ENABLED", "true")
    monkeypatch.setattr(main, "AsyncOpenAI", FakeOpenAI)

    async def ask_web() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
            return await client.post(
                "/api/v1/help",
                json={"question": "What is new in Python?", "mode": "web"},
                headers={"Authorization": f"Bearer {_token()}"},
            )

    response = asyncio.run(ask_web())

    assert response.status_code == 200
    assert response.json()["answer"] == "A web answer."
    assert response.json()["sources"] == [{"title": "Example source", "url": "https://example.test"}]
    assert calls[0]["input"] == "What is new in Python?"
    assert calls[0]["tools"] == [{"type": "web_search"}]
    assert calls[0]["store"] is False
    assert "ticket" not in str(calls[0]).lower()


def test_knowledge_help_requires_explicit_external_context_opt_in(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_KNOWLEDGE_CONTEXT_ENABLED", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    async def unexpected_mcp_call(*args, **kwargs):
        raise AssertionError("Knowledge retrieval must not happen when external sharing is disabled.")

    monkeypatch.setattr(main, "_call_mcp_as_user", unexpected_mcp_call)

    async def ask_knowledge() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
            return await client.post(
                "/api/v1/help",
                json={"question": "How do I reset a password?", "mode": "knowledge"},
                headers={"Authorization": f"Bearer {_token()}"},
            )

    response = asyncio.run(ask_knowledge())

    assert response.status_code == 503
    assert "disabled" in response.json()["detail"]


def test_knowledge_help_distinguishes_total_documents_from_retrieved_sources(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_KNOWLEDGE_CONTEXT_ENABLED", "true")
    received: dict[str, object] = {}

    async def fake_mcp(principal, name: str, arguments: dict[str, object]):
        assert name == "search_knowledge"
        assert arguments["limit"] == 5
        return [
            {
                "text": f"Excerpt {index}.",
                "citation": {
                    "title": f"Guide {index}",
                    "source": f"guide-{index}.md",
                    "page": None,
                },
            }
            for index in range(1, 6)
        ]

    async def fake_generate(question: str, context: str, language: str | None, web_search: bool = False):
        received["context"] = context
        return "There are 30 indexed documents.", []

    monkeypatch.setattr(main, "_call_mcp_as_user", fake_mcp)
    monkeypatch.setattr(main, "_rag_service", lambda: SimpleNamespace(list_documents=lambda: [{}] * 30))
    monkeypatch.setattr(main, "_generate_answer", fake_generate)

    async def ask_knowledge() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
            return await client.post(
                "/api/v1/help",
                json={"question": "How many documents are in the knowledge base?", "mode": "knowledge"},
                headers={"Authorization": f"Bearer {_token()}"},
            )

    response = asyncio.run(ask_knowledge())

    assert response.status_code == 200
    assert response.json()["knowledge_document_count"] == 30
    assert len(response.json()["sources"]) == 5
    assert "30 indexed documents in total" in received["context"]
    assert "not the complete inventory" in received["context"]


def test_ticket_help_requires_explicit_ticket_data_opt_in(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_TICKET_CONTEXT_ENABLED", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    async def unexpected_mcp_call(*args, **kwargs):
        raise AssertionError("Ticket retrieval must not happen when external sharing is disabled.")

    monkeypatch.setattr(main, "_call_mcp_as_user", unexpected_mcp_call)

    async def ask_ticket() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
            return await client.post(
                "/api/v1/help",
                json={"question": "Can you help?", "mode": "ticket", "ticket_id": 42},
                headers={"Authorization": f"Bearer {_token()}"},
            )

    response = asyncio.run(ask_ticket())

    assert response.status_code == 503
    assert "disabled" in response.json()["detail"]


def test_ticket_help_shares_only_authorized_ticket_fields_when_opted_in(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_TICKET_CONTEXT_ENABLED", "true")
    monkeypatch.delenv("OPENAI_KNOWLEDGE_CONTEXT_ENABLED", raising=False)
    received: dict[str, object] = {}

    async def fake_mcp(principal, name: str, arguments: dict[str, object]):
        received.setdefault("calls", []).append(name)
        assert principal.subject == "test-user"
        assert name == "get_ticket"
        return {
            "id": 918273,
            "title": "VPN unavailable",
            "description": "A test description without personal data.",
            "category": "Network",
            "status": "Open",
            "priority": "Normal",
            "createdById": "PRIVATE-REQUESTER-ID",
            "assignedToId": "PRIVATE-AGENT-ID",
        }

    async def fake_generate(question: str, context: str, language: str | None, web_search: bool = False):
        received["question"] = question
        received["context"] = context
        return "Suggested answer.", []

    monkeypatch.setattr(main, "_call_mcp_as_user", fake_mcp)
    monkeypatch.setattr(main, "_generate_answer", fake_generate)

    async def ask_ticket() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
            return await client.post(
                "/api/v1/help",
                json={"question": "What can I try?", "mode": "ticket", "ticket_id": 918273},
                headers={"Authorization": f"Bearer {_token()}"},
            )

    response = asyncio.run(ask_ticket())

    assert response.status_code == 200
    assert received["calls"] == ["get_ticket"]
    context = str(received["context"])
    assert "VPN unavailable" in context
    assert "PRIVATE-REQUESTER-ID" not in context
    assert "PRIVATE-AGENT-ID" not in context
    assert "918273" not in context


def test_ticket_copilot_requires_opt_in_and_agent_role(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_TICKET_CONTEXT_ENABLED", raising=False)
    calls: list[str] = []

    async def fake_mcp(*args, **kwargs):
        calls.append("ticket")
        raise AssertionError("Ticket API must not be called without sharing opt-in.")

    monkeypatch.setattr(main, "_call_mcp_as_user", fake_mcp)

    async def requests() -> tuple[httpx.Response, httpx.Response]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
            requester = await client.post(
                "/api/v1/agent/tickets/42/copilot",
                headers={"Authorization": f"Bearer {_token()}"},
            )
            agent = await client.post(
                "/api/v1/agent/tickets/42/copilot",
                headers={"Authorization": f"Bearer {_token('Agent')}"},
            )
            return requester, agent

    requester, agent = asyncio.run(requests())

    assert requester.status_code == 403
    assert agent.status_code == 503
    assert calls == []
    path_labels = {
        sample.labels["path"]
        for metric in HTTP_REQUESTS.collect()
        for sample in metric.samples
        if sample.name == "service_desk_http_requests_total"
    }
    assert "/api/v1/agent/tickets/{ticket_id}/copilot" in path_labels
    assert all("918273" not in path for path in path_labels)


def test_ticket_copilot_sends_only_allowlisted_ticket_fields_and_optional_kb(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_TICKET_CONTEXT_ENABLED", "true")
    monkeypatch.delenv("OPENAI_KNOWLEDGE_CONTEXT_ENABLED", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    received: dict[str, object] = {}

    async def fake_mcp(principal, name: str, arguments: dict[str, object]):
        received.setdefault("mcp_calls", []).append(name)
        assert principal.subject == "test-user"
        assert name == "get_ticket"
        return {
            "id": 918273,
            "title": "VPN unavailable",
            "description": "A test description without personal data.",
            "category": "Network",
            "status": "Open",
            "priority": "Normal",
            "createdById": "PRIVATE-REQUESTER-ID",
            "assignedToId": "PRIVATE-AGENT-ID",
        }

    class FakeResponses:
        async def create(self, **kwargs):
            received["request"] = kwargs
            return SimpleNamespace(
                output_text=json.dumps(
                    {
                        "summary": "VPN connection fails.",
                        "suggested_category": "Network",
                        "suggested_priority": "Normal",
                        "priority_rationale": "The reported impact is limited.",
                        "missing_information": ["VPN error code"],
                        "reply_draft": "Please share the VPN error code.",
                    }
                ),
                usage=SimpleNamespace(input_tokens=42, output_tokens=25),
            )

    class FakeOpenAI:
        def __init__(self):
            self.responses = FakeResponses()

    monkeypatch.setattr(main, "_call_mcp_as_user", fake_mcp)
    monkeypatch.setattr(main, "_openai_client", FakeOpenAI)

    async def ask_copilot() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
            return await client.post(
                "/api/v1/agent/tickets/918273/copilot",
                headers={"Authorization": f"Bearer {_token('Agent')}"},
            )

    response = asyncio.run(ask_copilot())

    assert response.status_code == 200
    assert received["mcp_calls"] == ["get_ticket"]
    request = received["request"]
    assert request["store"] is False
    response_format = request["text"]["format"]
    assert response_format["type"] == "json_schema"
    assert response_format["strict"] is True
    assert set(response_format["schema"]["required"]) == set(response_format["schema"]["properties"])
    prompt = str(request["input"])
    assert "VPN unavailable" in prompt
    assert "PRIVATE-REQUESTER-ID" not in prompt
    assert "PRIVATE-AGENT-ID" not in prompt
    assert "918273" not in prompt
    assert "Approved knowledge snippets:\nNo matching knowledge found." in prompt
    assert "Never infer total document counts from them" in request["instructions"]
    assert response.json()["suggested_priority"] == "Normal"


def test_ticket_copilot_reports_kb_inventory_separately_from_retrieved_sources(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_TICKET_CONTEXT_ENABLED", "true")
    monkeypatch.setenv("OPENAI_KNOWLEDGE_CONTEXT_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    async def fake_mcp(principal, name: str, arguments: dict[str, object]):
        if name == "get_ticket":
            return {
                "id": 42,
                "title": "VPN unavailable",
                "description": "A test description.",
                "category": "Network",
                "status": "Open",
                "priority": "Normal",
            }
        assert name == "search_knowledge"
        return [
            {
                "text": "A retrieved excerpt.",
                "citation": {
                    "title": "VPN guide",
                    "source": "vpn.md",
                    "page": None,
                    "version": 1,
                    "chunk_id": "chunk-1",
                },
            }
        ]

    class FakeResponses:
        async def create(self, **kwargs):
            return SimpleNamespace(
                output_text=json.dumps(
                    {
                        "summary": "The VPN connection is unavailable.",
                        "suggested_category": "Network",
                        "suggested_priority": "Normal",
                        "priority_rationale": "The impact is not yet established.",
                        "missing_information": [],
                        "reply_draft": "Please share the VPN error message.",
                    }
                ),
                usage=None,
            )

    class FakeOpenAI:
        def __init__(self):
            self.responses = FakeResponses()

    monkeypatch.setattr(main, "_call_mcp_as_user", fake_mcp)
    monkeypatch.setattr(main, "_rag_service", lambda: SimpleNamespace(list_documents=lambda: [{}] * 30))
    monkeypatch.setattr(main, "_openai_client", FakeOpenAI)

    async def ask_copilot() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
            return await client.post(
                "/api/v1/agent/tickets/42/copilot",
                headers={"Authorization": f"Bearer {_token('Agent')}"},
            )

    response = asyncio.run(ask_copilot())

    assert response.status_code == 200
    assert response.json()["knowledge_document_count"] == 30
    assert len(response.json()["sources"]) == 1
