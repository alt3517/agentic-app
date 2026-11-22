# Python FastAPI AI service

FastAPI provides authenticated RAG search, OpenAI help, Agent/Admin ticket copilot, Admin document APIs, read-only MCP tools, and Prometheus metrics. The VS Code workspace selects this project's `.venv` interpreter.

## Requirements and setup

- Python 3.12
- Qdrant (the repository Compose file provides it)
- A local HTTPS certificate exported at `..\dev-certs\localhost.pem` and `..\dev-certs\localhost.key`

Create the virtual environment and install dependencies from this directory:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -r test-requirements.txt
```

From the repository root, create and trust the local certificate:

```powershell
New-Item -ItemType Directory -Force dev-certs | Out-Null
dotnet dev-certs https --trust
dotnet dev-certs https --export-path dev-certs\localhost.pem --format PEM --no-password
```

Set `AI_JWT_SIGNING_KEY` to the same value configured in MVC. Set `OPENAI_API_KEY` and `OPENAI_MODEL` to enable generation and web search. RAG reranking is enabled by default; set `RERANKING_ENABLED=false` to skip it on resource-constrained systems. The first RAG search downloads the configured multilingual INT8 reranker (about 570 MB) into `EMBEDDING_CACHE_DIR`. `run.ps1` starts TLS on `https://localhost:8000`; it configures the MVC API at `https://localhost:7161` and verifies its certificate using the exported PEM. It does not disable TLS verification.

Ticket, knowledge-base, and web sharing to OpenAI is disabled by default. Enable `OPENAI_TICKET_CONTEXT_ENABLED`, `OPENAI_KNOWLEDGE_CONTEXT_ENABLED`, or `WEB_SEARCH_ENABLED` only after approving the relevant data flow. Ticket copilot requires the ticket sharing opt-in; knowledge excerpts are sent only when the separate knowledge opt-in is also enabled. After editing `.env`, run `.\scripts\Apply-OpenAIFlags.ps1` from the repository root. It applies the flags from that file, recreates only the AI service, and verifies the runtime values and health. OpenAI requests set `store=false`, which is not a provider zero-retention guarantee.

For local development, start Qdrant with `docker compose up -d qdrant` from the repository root, then start MVC and FastAPI:

```powershell
.\run.ps1
```

API docs: <https://localhost:8000/docs>. See the [repository README](../README.md) for full Docker usage and configuration.

## APIs

- `POST /api/v1/help`: `knowledge`, `ticket`, or `web` mode.
- `POST /api/v1/agent/tickets/{ticket_id}/copilot`: Agent/Admin-only triage recommendation and reply draft; it does not mutate or send a ticket.
- `POST /api/v1/rag/search`: hybrid search with citations.
- `/api/v1/admin/documents`: Admin-only upload, list, and delete operations.
- `POST /api/v1/admin/reindex`: Admin-only reindex operation.
- `/mcp`: authenticated Streamable HTTP MCP server exposing only ticket search/read and knowledge search tools.
- `/health`: service health endpoint.
- Prometheus metrics are served on the internal `PROMETHEUS_ADDR:PROMETHEUS_PORT` listener (Compose: `0.0.0.0:8001`, not host-published). Metrics contain aggregate timings, counts, token totals, and bounded route/operation labels; they exclude request bodies, ticket identifiers, and query text.
- Uvicorn access logs are disabled and HTTPX/HTTPcore loggers are set to WARNING (warnings and errors remain visible). The internal ticket search sends its query in a JSON body, not a URL; the local smoke test confirmed the request body marker was absent from container logs.

Knowledge retrieval combines Qdrant vector search and SQLite FTS5 lexical search with Reciprocal Rank Fusion (RRF, `k=5`), then reranks up to 20–40 candidates with the local `BAAI/bge-reranker-v2-m3-int8` cross-encoder (Apache-2.0). Query text and candidate documents are scored locally; no reranking API receives them. Returned scores are raw reranker scores, not probabilities. Thirty synthetic bilingual articles are seeded into an empty index. Ticket data is fetched live from the MVC API using the user's signed token; it is not indexed. See [Qdrant hybrid search guidance](https://qdrant.tech/documentation/search-tuning/hybrid-search/), the [FastEmbed supported model list](https://qdrant.github.io/fastembed/examples/Supported_Models/), and the [BGE reranker model card](https://huggingface.co/BAAI/bge-reranker-v2-m3).

## Tests and retrieval evaluation

From this directory:

```powershell
python -m pytest
python evaluate_retrieval.py
```

The test suite uses in-memory Qdrant and deterministic embedding/reranking fixtures. It checks the external-sharing gates and ensures ticket identifiers, user IDs, and search text are not included in copilot prompts, metrics, or request URLs. Retrieval evaluation uses the configured embedding, reranker, and Qdrant instance against 20 labeled bilingual queries.

## Monitoring

The repository Compose setup includes Prometheus and Grafana. Grafana provisions the **Service Desk AI Operations** dashboard with HTTP 5xx rate and p95 latency, RAG outcomes/latency, OpenAI operations/token rate, copilot usage, exporter health, and process memory/CPU. Prometheus retains 15 days by default. Both UIs are bound to localhost. The optional `ngrok` Compose profile exposes Grafana only; its dashboard queries Prometheus over the Docker network, so Prometheus does not need a public endpoint. Grafana authentication stays enabled. Prometheus and the unauthenticated metrics listener must not be exposed directly.
