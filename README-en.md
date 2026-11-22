# Service Desk AI — Local MVP

A working ASP.NET Core MVC ticket system with a separate Python/FastAPI AI service. The MVP includes tickets, a knowledge base, RAG search, read-only MCP tools, and OpenAI assistance. It is for local development and evaluation, not production.

## Features

- **MVC ticket system:** registration, sign-in, and `Requester`, `Agent`, and `Admin` roles; ticket creation, search, and management with server-side authorization.
- **AI help:** `/Help` answers questions about the knowledge base, tickets visible to the user, or the web. AI only proposes answers; it does not create, update, or send tickets.
- **AI agent copilot:** Agents/Admins can request category/priority suggestions, missing-information prompts, and a cited reply draft from a ticket. It never updates the ticket or sends the draft.
- **Hybrid RAG:** multilingual FastEmbed embeddings, Qdrant vector search, SQLite FTS5 lexical search, and Reciprocal Rank Fusion. Answers include citations.
- **Knowledge base:** 30 synthetic Italian/English articles are included. Admins can upload and delete TXT, MD, PDF, and DOCX files (up to 5 MB) at `/KnowledgeBase`.
- **MCP:** Streamable HTTP endpoint `/mcp` exposes read-only ticket search/read and knowledge search tools. Ticket access always goes through the MVC API and its authorization checks; tickets are not indexed in RAG.
- **OpenAI:** Responses API and web search. `OPENAI_API_KEY` is optional to start the other services but required to generate AI answers. Web mode sends only the question to OpenAI, not ticket context.
- **Operations monitoring:** Prometheus metrics for HTTP requests/errors, p95 latency, RAG, OpenAI usage/tokens, copilot activity, and process resources; a provisioned Grafana dashboard visualizes them. Qdrant usage telemetry and Grafana analytics reporting are disabled.

Document retrieval, Qdrant, SQLite FTS5, FastEmbed, and its embedding model are open-source components; OpenAI generation and web search are proprietary services. Knowledge-base documents do not have per-document ACLs: all authenticated users can search uploaded content. Do not upload confidential documents until their access requirements are addressed.

## Run locally with Docker Desktop

Prerequisites: Docker Desktop with Compose and the .NET 10 SDK to create and trust a local HTTPS development certificate. Python is not required to run the containers.

1. From the repository root, create and trust a local certificate:

   ```powershell
   New-Item -ItemType Directory -Force dev-certs | Out-Null
   dotnet dev-certs https --trust
   dotnet dev-certs https --export-path dev-certs\localhost.pem --format PEM --no-password
   ```

   Approve the trust prompt from Windows. The PEM files include the private key, are excluded from Git, and must only be used locally.

2. Prepare the configuration and edit `.env`:

   ```powershell
   Copy-Item .env.example .env
   ```

   Set `AI_JWT_SIGNING_KEY` to a random secret of at least 32 bytes. Choose distinct, strong values for `DEMO_ADMIN_PASSWORD`, `DEMO_AGENT_PASSWORD`, and `GRAFANA_ADMIN_PASSWORD`. `OPENAI_API_KEY` enables model access, but context sharing is still disabled until explicitly enabled with `OPENAI_TICKET_CONTEXT_ENABLED`, `OPENAI_KNOWLEDGE_CONTEXT_ENABLED`, and `WEB_SEARCH_ENABLED`. Keep them `false` until provider and data-processing approval. For optional remote Grafana access, also set `NGROK_AUTHTOKEN`, `NGROK_GRAFANA_DOMAIN`, and `GRAFANA_ROOT_URL` as described below.

3. Build and start the services:

   ```powershell
   docker compose up --build -d
   docker compose ps
   docker compose logs -f agentic-app
   ```

   On first startup, FastEmbed downloads its model and indexes the sample articles; the health check may take several minutes to become healthy.

   After changing the sharing flags in `.env`, apply them with the script below. It explicitly uses the project's `.env`, avoids shell environment overrides, and verifies the runtime values:

   ```powershell
   .\scripts\Apply-OpenAIFlags.ps1
   ```

   The script recreates only `agentic-app` and waits for it to become healthy. `docker compose build` alone does not update an existing container's environment. When knowledge sharing is enabled, questions and retrieved excerpts may be sent to OpenAI; enable it only after approving that data flow.

4. Open <https://localhost:7161> and sign in with the Admin or Agent account configured in `.env`. The **Monitoring** menu (Admin only) links to the Grafana dashboard and Prometheus targets; Grafana requires user `admin` and `GRAFANA_ADMIN_PASSWORD`. The **Service Desk AI Operations** dashboard is provisioned automatically. FastAPI health and OpenAPI endpoints are at <https://localhost:8000/health> and <https://localhost:8000/docs>.

### Optional remote Grafana access with ngrok

Grafana reads Prometheus over the Docker network, so the Grafana tunnel is sufficient to view dashboards remotely; the Prometheus UI is not exposed. Grafana authentication remains enabled (`admin` and `GRAFANA_ADMIN_PASSWORD`).

1. Get the ngrok authtoken and reserved HTTPS domain from your ngrok dashboard. In `.env`, set `NGROK_AUTHTOKEN`, `NGROK_GRAFANA_DOMAIN` (host only, e.g. `name.ngrok-free.app`), and `GRAFANA_ROOT_URL` (full URL with trailing slash, e.g. `https://name.ngrok-free.app/`). Use the same domain in both URL settings.
2. Start the tunnel:

   ```powershell
   docker compose --profile ngrok up -d ngrok-grafana
   docker compose logs -f ngrok-grafana
   ```

3. Open the configured domain and sign in as `admin` with `GRAFANA_ADMIN_PASSWORD`. The tunnel is publicly reachable over the Internet: share the domain only with authorized users and keep a strong password. ngrok request inspection is disabled.

Stop the tunnel with `docker compose --profile ngrok stop ngrok-grafana`. Prometheus remains local-only; the ngrok tunnel is not started by the regular `docker compose up`.

Stop the containers with `docker compose down`. SQLite databases, downloaded FastEmbed models, Qdrant, Prometheus, and Grafana data remain in local Docker volumes. `docker compose down -v` removes all these volumes and deletes the data.

## APIs and integrations

- Internal ticket API: `main-app` enforces identity and permissions; it is reachable only on the Compose network and requires a short-lived signed JWT.
- FastAPI provides `/api/v1/help`, `/api/v1/rag/search`, Admin document APIs, and MCP Streamable HTTP at `/mcp`.
- Agent copilot: `POST /api/v1/agent/tickets/{ticket_id}/copilot`, restricted to Agent/Admin and still subject to MVC ticket authorization.
- The Prometheus exporter listens on container port `8001`, which is not published to the host; Prometheus scrapes it over the Docker network.
- The MVC UI requests a temporary token through an antiforgery-protected endpoint and keeps it in browser memory only.
- Python-to-MVC calls use HTTP on the unpublished Docker network with a JWT. This is a local-demo simplification, not a configuration for shared deployments.
- With defaults, tickets, knowledge excerpts, and web queries are **not sent** to OpenAI. Enabling `OPENAI_TICKET_CONTEXT_ENABLED` allows ticket help and copilot to send authorized ticket fields; copilot omits ticket ID, requester ID, and assignee ID. `OPENAI_KNOWLEDGE_CONTEXT_ENABLED` separately allows document excerpts to be sent; `WEB_SEARCH_ENABLED` separately allows the question alone to be sent to OpenAI web search. All three are independent and off by default.
- Responses API calls set `store=false`; this is not a provider zero-retention guarantee. Do not send real data until privacy, provider, region, retention, and minimization requirements are approved.
- Metrics and dashboards do not record prompts, ticket text, names, requester/ticket IDs, or query strings. HTTP metrics use route templates; Uvicorn access logs are disabled, while HTTPX/HTTPcore and MVC HTTP lifecycle loggers are set to Warning (warnings and errors remain visible). Internal ticket searches send free text in a JSON body, not the URL query; the local smoke test confirmed the body marker did not appear in container logs. The exporter is on a dedicated internal Docker network. Prometheus and Grafana remain bound to localhost; the optional ngrok profile exposes only Grafana, which requires sign-in. Prometheus has no authentication and must not be exposed directly.

## Tests

```powershell
dotnet test main-app.Tests\main-app.Tests.csproj
Set-Location agentic-app
python -m pip install -r test-requirements.txt
python -m pytest
```

**Current local verification:** 3 MVC integration tests and 23 FastAPI tests passed, including opt-in, ticket-field minimization, and metrics-without-query-or-ID tests; Compose, Prometheus scraping, and the 12-panel Grafana dashboard were verified. The local smoke test confirmed that the submitted JSON body marker did not appear in container logs. Sharing endpoints without opt-in return HTTP 503 before retrieving tickets or calling OpenAI. On 20 synthetic bilingual questions with one expected source each, retrieval plus reranking scored Recall@5 **1.00** and MRR@5 **0.975**: 19 sources ranked first and one ranked second (the lost-laptop query). RRF alone scored MRR@5 **0.950**. This is a demo benchmark, not a guarantee for the client's corpus. Live OpenAI calls were not tested because no key is configured and sharing is disabled.

Evaluate retrieval against the included 20 bilingual queries (requires the models and a configured Qdrant instance):

```powershell
python evaluate_retrieval.py
```

## Python development without Docker

Use Python 3.12 and the virtual environment associated with [agentic-app](./agentic-app/README.md):

```powershell
Set-Location agentic-app
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -r test-requirements.txt
```

Start Qdrant from the repository root with `docker compose up -d qdrant`; start MVC with `dotnet run --launch-profile https` from `main-app`; then start FastAPI with `.\run.ps1` from `agentic-app`. Configure `AI_JWT_SIGNING_KEY`, `OPENAI_API_KEY`, and `OPENAI_MODEL` in the environment. `run.ps1` verifies the MVC certificate using the local PEM; do not disable TLS verification.

## Limitations and security

- Compose publishes ports only on `127.0.0.1`; development certificates and secrets are not suitable for production.
- The MVC ticket API remains authoritative and enforces requester/agent/admin permissions. MCP has no write tools.
- Authenticated users share the document index; implement document/tenant ACLs before adding content with different access permissions.
- AI can be wrong; verify citations and every suggestion before acting.
- HTTPS protects both public endpoints. Python-to-MVC traffic uses HTTP confined to the unpublished Compose network. Shared environments need internal TLS, secret management, network controls, logging, and operational review.

## Documents

- [Project plan in English](./plan-en.md)
- [Piano di progetto in italiano](./plan.md)
- [README in italiano](./README.md)
