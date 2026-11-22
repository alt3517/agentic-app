# Project Plan — Service Desk AI

**Status:** MVP implemented; local Docker verification complete, OpenAI flows still unverified  
**Audience:** client and development team  
**Current environment:** local Docker Compose demo; not production-ready

## 1. Goal

Demonstrate how a Python/FastAPI AI service can complement an ASP.NET Core MVC ticket system with document retrieval and assistance while MVC retains identity, permissions, transactional data, and business rules. AI provides sourced suggestions; it performs no autonomous write actions.

## 2. Implemented capabilities

- **Ticket system:** registration and sign-in; `Requester`, `Agent`, and `Admin` roles; ticket creation, search, and management with MVC authorization.
- **AI help (`/Help`):** answers grounded in the knowledge base, tickets the user may view, or OpenAI web search. Ticket help sends authorized ticket fields and retrieved context to the generative model.
- **Agent copilot:** for Agents/Admins, suggests a summary, category/priority, missing information, and a cited reply draft; it does not update the ticket or send the draft.
- **Knowledge base (`/KnowledgeBase`):** Admin UI to upload and delete TXT, Markdown, PDF, and DOCX documents up to 5 MB.
- **Hybrid RAG:** overlapping chunks, multilingual FastEmbed embeddings, Qdrant, and SQLite FTS5 lexical search; Reciprocal Rank Fusion (`k=5`) combines rankings, then a local multilingual INT8 cross-encoder reranks up to 40 candidates. The Apache-2.0 reranker (~570 MB) downloads on first use; queries and documents stay local. Answers return citations with document, version, and PDF page where available.
- **Samples and evaluation:** 30 synthetic Italian/English articles and 20 evaluation queries with one expected source each. Latest local run: Recall@5 **1.00** and MRR@5 **0.975** with reranking (19 sources ranked first; the lost-laptop query ranked second), compared with **0.950** for RRF alone. This demo benchmark is not a guarantee for the client corpus.
- **Read-only MCP:** authenticated Streamable HTTP `/mcp` endpoint with ticket search/read and knowledge search tools. No write tools are exposed.
- **OpenAI:** Responses API and web search tool. Web mode sends only the question; it excludes tickets and MCP context.
- **Demo deployment:** Docker Compose with MVC and FastAPI over HTTPS, Qdrant, persistent SQLite, and host ports bound to `127.0.0.1`.
- **Observability:** Prometheus collects HTTP/RAG/OpenAI/copilot counters and histograms; Grafana visualizes error rate, p95 latency, token rate, exporter health, and process resources. Administrators can open the Grafana dashboard and Prometheus targets from the MVC **Monitoring** menu. Local Prometheus retention: 15 days.

Open-source RAG components include FastEmbed and its multilingual embedding model, Qdrant, and SQLite FTS5. OpenAI generation and web search are proprietary services. An OpenAI key is required to generate answers but not to start the other services.

## 3. Architecture and data boundaries

```text
Browser ─HTTPS→ MVC :7161 ───────→ ticket SQLite
   └─────HTTPS→ FastAPI :8000 ───→ Qdrant + SQLite FTS5 (knowledge base)
                                  └─JWT→ MVC :8081 (Compose network, unpublished HTTP)
                                       └─read-only MCP / authorized ticket API
FastAPI ─HTTPS→ OpenAI Responses / web search
```

- MVC is the sole system of record for tickets. The AI service does not access the MVC database.
- The internal ticket API filters by role/user and requires a short-lived, MVC-signed JWT. It is reachable only on the Compose network; port `8081` is not published to the host.
- Tickets are not copied into RAG. Ticket mode reads them live through MCP/API and may send authorized fields to the generative model.
- OpenAI sharing has separate opt-ins for tickets (`OPENAI_TICKET_CONTEXT_ENABLED`), knowledge-base content (`OPENAI_KNOWLEDGE_CONTEXT_ENABLED`), and web (`WEB_SEARCH_ENABLED`); all default to off. Copilot sends only ticket title, description, current category/priority, and status—never ticket, requester, or assignee IDs. Knowledge citations/snippets are sent only with the separate knowledge opt-in.
- OpenAI requests set `store=false`, which is not a provider zero-retention guarantee. There is no automatic PII/secret detector or redactor for free text; do not send real data without approval and minimization.
- The knowledge index is shared across authenticated users: per-document, tenant, and category ACLs are not implemented. Uploaded files and indexed text are stored in the local data volume.
- The browser receives a temporary JWT from an antiforgery-protected MVC endpoint and calls FastAPI over HTTPS; the OpenAI key stays in the service.
- FastAPI-to-MVC traffic uses HTTP only on the unpublished Docker network. This is a local-demo simplification only; do not reuse it in shared or production environments.
- OpenAI web mode receives only the user's question. Ticket content is excluded from web search.
- Metric labels are limited to method/route template/status/operation/outcome and contain no prompts, queries, text, names, or ticket/user IDs. Uvicorn access logs are disabled; HTTPX/HTTPcore and MVC HTTP lifecycle loggers are set to Warning, leaving warnings and errors visible. Internal ticket search text travels in a JSON body, not the URL; the local smoke test confirmed the body marker did not appear in container logs. The exporter listens on internal port `8001` on a private Docker metrics network; Prometheus/Grafana remain published only on localhost. The optional ngrok profile forwards Grafana only (login required); Prometheus remains internal and supplies Grafana dashboards over Docker networking. Qdrant usage telemetry and Grafana analytics/reporting are disabled.

## 4. Current stack and configuration

| Area | Current choice |
|---|---|
| UI and ticket system | ASP.NET Core MVC / .NET 10, Identity, SQLite |
| AI API and orchestration | Python 3.12, FastAPI |
| Retrieval | Multilingual FastEmbed, Qdrant vector search, SQLite FTS5 lexical search, Reciprocal Rank Fusion |
| Tools | MCP SDK, Streamable HTTP, read-only tools only |
| Model and web search | OpenAI Responses API, configurable model (`gpt-6-luna` default) |
| Local execution | Docker Compose, development HTTPS certificate, local volumes; optional ngrok tunnel for Grafana |

Main configuration is in `.env` (never commit it): `AI_JWT_SIGNING_KEY` of at least 32 bytes; distinct strong Admin, Agent, and Grafana passwords; `OPENAI_API_KEY` and the opt-ins for approved AI features. For ngrok, also set the authtoken, reserved domain, and public Grafana URL. Published ports remain localhost-only; Prometheus is not tunneled. Windows instructions are in the [English README](./README-en.md).

## 5. Security, privacy, and limitations

- HTTPS is enabled on public MVC and FastAPI endpoints. Docker certificates are for development and should only be trusted on the local machine.
- The internal HTTP connection is JWT-authenticated but does not encrypt traffic; an unpublished local network is not equivalent to TLS.
- By default, no ticket/knowledge context or web query is sent to OpenAI. Enable opt-ins only after provider, region, retention, minimization, and legal-basis approval; user questions may themselves contain sensitive data. Ticket help sends authorized fields; web search sends only the question.
- All authenticated users can search the same documents. Confidential content requires ACLs before retrieval and cross-role/tenant negative tests.
- MCP is read-only and forwards ticket requests to MVC with the user's token; the model cannot choose identity or permissions.
- AI can be wrong or provide insufficient citations. Users must verify sources and suggestions; there are no autonomous writes or sends.
- Monitoring is a demonstration baseline and does not establish an SLA or cost. Prometheus has no authentication but is localhost-only; the exporter is confined to the internal metrics network. Alerting, internal TLS, secret store, rate limiting, operational audit, document policy, backup/restore, and dedicated load/security tests remain.

## 6. Verification and next steps

**Verified locally:** 3 MVC integration tests and 23 FastAPI tests passed; `docker compose config --quiet` validates the updated Compose configuration. FastAPI/Qdrant/Prometheus/Grafana health, Prometheus scraping, the 12-panel dashboard, and HTTPS smoke tests were verified in the previous local deployment. Tests cover opt-ins, forwarded fields, and absence of query/IDs from URLs and metrics; the previous smoke test confirmed the request body text was absent from container logs. Sharing requests without opt-in return HTTP 503 before ticket retrieval or OpenAI calls. Retrieval evaluation with FastEmbed 0.9.1 on 20 bilingual questions scored Recall@5 **1.00** and MRR@5 **0.975** with reranking (19 sources ranked first and the lost-laptop query ranked second; **0.950** for RRF alone) using in-memory Qdrant. Live OpenAI was not tested: no key is configured and sharing remains disabled.

| Priority | Work | Completion criterion |
|---|---|---|
| 1 | Rebuild Compose with Prometheus/Grafana and privacy-safe defaults | **Complete:** services healthy, Prometheus scrape `up`, dashboard available, HTTPS passed |
| 2 | Verify copilot end to end with synthetic data and an approved OpenAI account | Pending: sharing is off by default; use demo data and an approved provider only |
| 3 | Verify PDF/DOCX upload, reindexing, and deletion with persistent Qdrant | Correct citations and updates after restart |
| 4 | Agree on data/security requirements before using real content | Client decisions on ACLs, OpenAI, retention, audit, and internal TLS |
| 5 | Estimate hardening and shared deployment separately | Threat model, infrastructure, and acceptance criteria approved |

## 7. Current exclusions

MCP writes, automatic ticket updates or replies, direct model access to the database, multi-tenancy, document ACLs, public/production deployment, training or fine-tuning on client data, and accuracy guarantees. These require separate approval and design.
