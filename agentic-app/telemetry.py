from __future__ import annotations

import os

from prometheus_client import Counter, Histogram, start_http_server


HTTP_REQUESTS = Counter(
    "service_desk_http_requests",
    "HTTP requests served by the agentic app.",
    ("method", "path", "status"),
)
HTTP_REQUEST_DURATION = Histogram(
    "service_desk_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ("method", "path"),
)
RAG_SEARCHES = Counter(
    "service_desk_rag_searches",
    "Knowledge-base searches by result outcome.",
    ("outcome",),
)
RAG_SEARCH_DURATION = Histogram(
    "service_desk_rag_search_duration_seconds",
    "Knowledge-base search duration in seconds.",
)
OPENAI_REQUESTS = Counter(
    "service_desk_openai_requests",
    "OpenAI requests by operation and API outcome.",
    ("operation", "outcome"),
)
OPENAI_REQUEST_DURATION = Histogram(
    "service_desk_openai_request_duration_seconds",
    "OpenAI request duration in seconds.",
    ("operation",),
)
OPENAI_TOKENS = Counter(
    "service_desk_openai_tokens",
    "OpenAI tokens reported by the API.",
    ("operation", "direction"),
)
TICKET_COPILOT_REQUESTS = Counter(
    "service_desk_ticket_copilot_requests",
    "Ticket copilot suggestions by outcome.",
    ("outcome",),
)
TICKET_COPILOT_DURATION = Histogram(
    "service_desk_ticket_copilot_duration_seconds",
    "Ticket copilot request duration in seconds.",
)


def start_metrics_server() -> tuple[object, object]:
    return start_http_server(
        port=int(os.getenv("PROMETHEUS_PORT", "8001")),
        addr=os.getenv("PROMETHEUS_ADDR", "127.0.0.1"),
    )
