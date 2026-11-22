# Piano di progetto — Service Desk AI

**Stato:** MVP implementato; verifica locale Docker completata, flussi OpenAI ancora da verificare  
**Destinatari:** cliente e team di sviluppo  
**Ambiente attuale:** demo locale Docker Compose; non pronto per la produzione

## 1. Obiettivo

Dimostrare come affiancare a un ticket system ASP.NET Core MVC un servizio Python/FastAPI per ricerca documentale e assistenza AI, lasciando a MVC identità, permessi, dati transazionali e regole applicative. L’AI fornisce suggerimenti con fonti; nessuna operazione di scrittura viene eseguita autonomamente.

## 2. Funzioni implementate

- **Ticket system:** registrazione e login; ruoli `Requester`, `Agent` e `Admin`; creazione, ricerca e gestione dei ticket con autorizzazione lato MVC.
- **AI help (`/Help`):** risposte basate sulla knowledge base, sui ticket che l’utente può vedere o su ricerca web OpenAI. Per richieste sui ticket, dati autorizzati e contenuti recuperati sono inviati al modello generativo.
- **Agent copilot:** per Agent/Admin propone triage (riepilogo, categoria/priorità, dati mancanti) e bozza di risposta con fonti; il ticket non viene aggiornato e la bozza non viene inviata.
- **Knowledge base (`/KnowledgeBase`):** pannello Admin per caricare ed eliminare file TXT, Markdown, PDF e DOCX fino a 5 MB.
- **RAG ibrido:** chunking con sovrapposizione, embedding multilingue FastEmbed, Qdrant e ricerca lessicale SQLite FTS5; Reciprocal Rank Fusion (`k=5`) combina le classifiche, poi un cross-encoder multilingue locale INT8 riordina fino a 40 candidati. Modello reranker Apache-2.0 (~570 MB), scaricato al primo uso; query e documenti restano locali. Le risposte restituiscono citazioni con documento, versione e pagina PDF quando disponibile.
- **Esempi e valutazione:** 30 articoli sintetici IT/EN e 20 query di valutazione con una fonte attesa ciascuna. Ultima esecuzione locale: Recall@5 **1,00** e MRR@5 **0,975** con reranking (19 fonti al primo posto; la query sul laptop smarrito al secondo), rispetto a **0,950** con il solo RRF. Benchmark dimostrativo, non garanzia sul corpus del cliente.
- **MCP read-only:** endpoint Streamable HTTP `/mcp`, protetto da JWT; strumenti per ricerca/lettura ticket e ricerca knowledge base. Non sono esposti strumenti di scrittura.
- **OpenAI:** Responses API e strumento web search. La modalità web invia solo la domanda; non include ticket o contesto MCP.
- **Deploy dimostrativo:** Docker Compose con MVC e FastAPI su HTTPS, Qdrant, SQLite persistente e porte host vincolate a `127.0.0.1`.
- **Osservabilità:** Prometheus raccoglie contatori e istogrammi HTTP/RAG/OpenAI/copilot; Grafana mostra error rate, p95, token rate, disponibilità exporter e risorse processo. Gli amministratori accedono alla dashboard e ai target Prometheus dal menu MVC **Monitoring**. Retention Prometheus locale: 15 giorni.

Componenti RAG open source: FastEmbed e modello di embedding multilingue, Qdrant e SQLite FTS5. Generazione e web search OpenAI sono servizi proprietari. La chiave OpenAI è necessaria per generare risposte, ma non per avviare gli altri servizi.

## 3. Architettura e confini dei dati

```text
Browser ─HTTPS→ MVC :7161 ───────→ SQLite ticket
   └─────HTTPS→ FastAPI :8000 ───→ Qdrant + SQLite FTS5 (knowledge base)
                                  └─JWT→ MVC :8081 (rete Compose, HTTP non pubblicato)
                                       └─MCP read-only / API ticket autorizzata
FastAPI ─HTTPS→ OpenAI Responses / web search
```

- MVC è l’unica fonte autorevole dei ticket. Il servizio AI non accede al database MVC.
- L’API ticket interna filtra i dati per ruolo/utente e richiede un JWT MVC firmato con scadenza breve. È accessibile solo sulla rete Compose e non pubblica la porta `8081` sull’host.
- I ticket non vengono copiati nell’indice RAG. La modalità ticket li recupera in tempo reale via MCP/API e può inviare al modello i campi autorizzati.
- L’invio a OpenAI è opt-in distinto per ticket (`OPENAI_TICKET_CONTEXT_ENABLED`), knowledge base (`OPENAI_KNOWLEDGE_CONTEXT_ENABLED`) e web (`WEB_SEARCH_ENABLED`); tutti disattivati per default. Il copilot invia solo titolo, descrizione, categoria/priorità correnti e stato, mai ID ticket, requester o assegnatario. Le citazioni KB vengono inviate al modello solo con l’opt-in knowledge.
- Le richieste OpenAI impostano `store=false`, che non è una garanzia di zero retention del provider. Non è implementato un rilevatore/redattore automatico di PII o segreti nei testi liberi: i dati reali non vanno inoltrati senza approvazione e minimizzazione.
- L’indice knowledge base è condiviso da tutti gli utenti autenticati: non esistono ancora ACL per documento, tenant o categoria. I file caricati sono conservati nel volume dati locale insieme al testo indicizzato.
- Il browser riceve un JWT temporaneo via endpoint MVC protetto da antiforgery e chiama FastAPI con HTTPS; la chiave OpenAI resta sul servizio.
- Il traffico FastAPI→API MVC usa HTTP solo nella rete Docker non pubblicata. È una semplificazione accettabile esclusivamente per la demo locale; non va riutilizzata in un ambiente condiviso o produttivo.
- La modalità web OpenAI riceve esclusivamente la domanda dell’utente. Il contenuto dei ticket non entra nella ricerca web.
- Le metriche hanno label limitate a metodo/route template/status/operazione/outcome; non contengono prompt, query, testi, nomi o ID ticket/utente. Gli access log Uvicorn sono disattivati; logger HTTPX/HTTPcore e log lifecycle HTTP MVC sono impostati a Warning, lasciando visibili warning ed errori. La query ticket interna viaggia nel body JSON, non nell’URL; lo smoke test ha verificato che il testo del body non appare nei log dei container. Exporter su porta interna `8001`, rete Docker metrics interna; Prometheus e Grafana restano pubblicati solo su localhost. Il profilo ngrok opzionale inoltra solo Grafana (login obbligatorio); Prometheus non viene esposto e alimenta la dashboard sulla rete Docker. Qdrant usage telemetry e Grafana analytics/reporting sono disabilitati.

## 4. Stack e configurazione

| Area | Scelta attuale |
|---|---|
| UI e sistema ticket | ASP.NET Core MVC / .NET 10, Identity, SQLite |
| API AI e orchestrazione | Python 3.12, FastAPI |
| Retrieval | FastEmbed multilingue, Qdrant vettoriale, SQLite FTS5 lessicale, Reciprocal Rank Fusion |
| Strumenti | MCP SDK, Streamable HTTP, soli strumenti read-only |
| Modello e ricerca web | OpenAI Responses API, modello configurabile (`gpt-6-luna` predefinito) |
| Esecuzione locale | Docker Compose, certificato HTTPS di sviluppo, volumi locali; tunnel ngrok opzionale per Grafana |

Configurazione principale in `.env` (mai versionare il file): `AI_JWT_SIGNING_KEY` con almeno 32 byte; password distinte e robuste per Admin, Agent e Grafana; `OPENAI_API_KEY` e gli opt-in per le funzioni AI approvate. Per ngrok servono inoltre authtoken, dominio riservato e URL pubblico di Grafana. Le porte restano pubblicate solo su localhost; Prometheus non viene tunnellizzato. I dettagli per Windows sono nel [README italiano](./README.md).

## 5. Sicurezza, privacy e limiti

- HTTPS è attivo sugli endpoint pubblici MVC e FastAPI. I certificati Docker sono di sviluppo e vanno fidati solo sul computer locale.
- Il collegamento HTTP interno è autenticato con JWT ma non cifra i dati: rete locale non pubblicata, non equivalente a un confine TLS.
- Per default, nessun contesto ticket/knowledge e nessuna query web viene inviata a OpenAI. Abilitare gli opt-in solo dopo approvazione di provider, regione, retention, minimizzazione e base giuridica; le domande inserite dagli utenti possono comunque contenere dati sensibili. Ticket help invia campi autorizzati; web search invia solo la domanda.
- Tutti gli utenti autenticati possono cercare gli stessi documenti. Prima di dati riservati servono ACL applicate prima del retrieval e test cross-ruolo/tenant.
- MCP è read-only e inoltra i ticket all’API MVC con il token dell’utente; il modello non sceglie identità o permessi.
- L’AI può produrre errori o citazioni non sufficienti. L’utente deve verificare fonti e suggerimenti; nessuna scrittura o invio autonomo.
- Il monitoraggio è un baseline dimostrativo, non certifica SLA o costi; Prometheus è senza autenticazione ma solo localhost, exporter accessibile sulla rete metrics interna. Mancano alerting, TLS interno, secret store, rate limiting, audit operativo, policy documentali, backup/restore e test di carico/sicurezza.

## 6. Verifica e prossimi passi

**Verificato localmente:** 3 test d’integrazione MVC e 23 test FastAPI superati; configurazione Compose validata con `docker compose config --quiet`; FastAPI/Qdrant/Prometheus/Grafana e dashboard a 12 pannelli erano stati verificati nel deployment locale precedente. I test verificano gli opt-in, i campi inoltrati e l’assenza di query/ID in URL e metriche; lo smoke test precedente ha verificato che il testo nel body non appare nei log dei container. Le chiamate sharing senza opt-in restituiscono HTTP 503 prima di recuperare ticket o chiamare OpenAI. Retrieval su 20 quesiti bilingui: Recall@5 **1,00** e MRR@5 **0,975** con reranking (19 fonti al primo posto, laptop smarrito al secondo; RRF solo: **0,950**), su Qdrant in memoria. OpenAI live non verificato: chiave assente e opt-in disattivati.

| Priorità | Attività | Criterio di completamento |
|---|---|---|
| 1 | Ricostruire e avviare Compose con Prometheus/Grafana e default privacy sicuri | **Completato:** servizi healthy, scrape Prometheus `up`, dashboard disponibile, HTTPS superato |
| 2 | Verificare il copilot end-to-end con dati sintetici e account OpenAI approvato | Da completare: condivisioni disattivate per default; usare solo dati demo e provider approvato |
| 3 | Verificare upload PDF/DOCX, reindicizzazione e cancellazione con Qdrant persistente | Citazioni corrette e dati aggiornati anche dopo restart |
| 4 | Concordare requisiti dati e security per eventuale uso di contenuti reali | Decisioni cliente su ACL, OpenAI, retention, audit e TLS interno |
| 5 | Stimare hardening e deployment condiviso separatamente | Threat model, infrastruttura e criteri di accettazione approvati |

## 7. Fuori ambito attuale

Scrittura MCP, aggiornamento o invio automatico di ticket, accesso diretto del modello al database, multi-tenancy, ACL documentali, deployment pubblico/produzione, training o fine-tuning su dati del cliente e garanzie di accuratezza. Tali funzioni richiedono approvazione e progettazione dedicate.
