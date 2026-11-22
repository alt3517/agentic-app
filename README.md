# Service Desk AI — MVP locale

Demo funzionante di un ticket system ASP.NET Core MVC con un servizio AI separato in Python/FastAPI. L’MVP include ticket, knowledge base, ricerca RAG, MCP read-only e assistenza con OpenAI. È pensato per sviluppo e valutazione locale, non per produzione.

## Funzionalità

- **Ticket system MVC:** registrazione, login e ruoli `Requester`, `Agent` e `Admin`; creazione, ricerca e gestione dei ticket con autorizzazioni lato server.
- **AI help:** pagina `/Help` per domande sulla knowledge base, ticket visibili all’utente e ricerca web. L’AI propone risposte; non crea, aggiorna o invia ticket.
- **AI agent copilot:** da un ticket l’Agent/Admin può ottenere suggerimenti di categoria/priorità, informazioni mancanti e una bozza di risposta con citazioni. Il ticket non viene modificato e la bozza non viene inviata.
- **RAG ibrido:** FastEmbed con embedding multilingue, Qdrant per ricerca vettoriale, SQLite FTS5 per ricerca lessicale e Reciprocal Rank Fusion per combinare i risultati. Le risposte includono citazioni.
- **Knowledge base:** 30 articoli sintetici IT/EN inclusi; gli Admin possono caricare ed eliminare file TXT, MD, PDF e DOCX (massimo 5 MB) da `/KnowledgeBase`.
- **MCP:** endpoint Streamable HTTP `/mcp` con soli strumenti read-only per ricerca/lettura ticket e ricerca documentale. I ticket passano sempre dall’API MVC e dai relativi controlli di accesso; non vengono indicizzati nel RAG.
- **OpenAI:** Responses API e web search. `OPENAI_API_KEY` è opzionale per avviare gli altri servizi, ma necessaria per generare risposte. La modalità web invia a OpenAI soltanto la domanda, senza contesto dei ticket.
- **Monitoraggio operativo:** metriche Prometheus per richieste/errori HTTP, latenza p95, RAG, utilizzo/token OpenAI, copilot e risorse del processo; dashboard Grafana preconfigurata. La telemetria di utilizzo di Qdrant e i report analitici Grafana sono disattivati.

Il recupero documentale, Qdrant, SQLite FTS5, FastEmbed e il relativo modello sono componenti open source; il modello generativo e la web search OpenAI sono servizi proprietari. Gli articoli della knowledge base non hanno ACL per singolo documento: tutti gli utenti autenticati possono cercare i contenuti caricati. Non caricare documenti riservati senza aver prima definito i permessi richiesti.

## Avvio locale con Docker Desktop

Prerequisiti: Docker Desktop con Compose e .NET 10 SDK per creare/trustare il certificato HTTPS di sviluppo. Python non serve per avviare i container.

1. Dalla root del repository crea e fida il certificato locale:

   ```powershell
   New-Item -ItemType Directory -Force dev-certs | Out-Null
   dotnet dev-certs https --trust
   dotnet dev-certs https --export-path dev-certs\localhost.pem --format PEM --no-password
   ```

   Conferma l’attendibilità quando Windows la richiede. I file PEM includono la chiave privata, sono esclusi da Git e vanno usati solo in locale.

2. Prepara la configurazione e modifica `.env`:

   ```powershell
   Copy-Item .env.example .env
   ```

   Imposta `AI_JWT_SIGNING_KEY` con un segreto casuale di almeno 32 byte e scegli password distinte e robuste per `DEMO_ADMIN_PASSWORD`, `DEMO_AGENT_PASSWORD` e `GRAFANA_ADMIN_PASSWORD`. `OPENAI_API_KEY` abilita la connessione al modello, ma le modalità di condivisione restano disattivate finché non vengono abilitate esplicitamente: `OPENAI_TICKET_CONTEXT_ENABLED`, `OPENAI_KNOWLEDGE_CONTEXT_ENABLED` e `WEB_SEARCH_ENABLED`. Mantienile `false` finché provider e trattamento dei dati non sono approvati. Per l’accesso remoto opzionale a Grafana, imposta anche `NGROK_AUTHTOKEN`, `NGROK_GRAFANA_DOMAIN` e `GRAFANA_ROOT_URL` come descritto sotto.

3. Costruisci e avvia i servizi:

   ```powershell
   docker compose up --build -d
   docker compose ps
   docker compose logs -f agentic-app
   ```

   Al primo avvio FastEmbed scarica il modello e indicizza gli articoli dimostrativi; l’health check può rimanere in avvio per alcuni minuti.

   Dopo aver modificato i flag di condivisione in `.env`, applicali con lo script che usa esplicitamente il `.env` del progetto, evita override ambientali e verifica i valori runtime:

   ```powershell
   .\scripts\Apply-OpenAIFlags.ps1
   ```

   Lo script ricrea solo `agentic-app` e attende che diventi healthy. `docker compose build` da solo non aggiorna l’ambiente di un container già avviato. Quando l’opzione knowledge è attiva, domande ed estratti recuperati possono essere inviati a OpenAI; abilitala solo dopo aver approvato questo flusso di dati.

4. Apri <https://localhost:7161> e accedi con l’account Admin o Agent definito in `.env`. Nel menu **Monitoring** (solo Admin) trovi il collegamento alla dashboard Grafana e ai target Prometheus; Grafana richiede l’utente `admin` e la password `GRAFANA_ADMIN_PASSWORD`. La dashboard **Service Desk AI Operations** è provisionata automaticamente. FastAPI espone health e OpenAPI su <https://localhost:8000/health> e <https://localhost:8000/docs>.

### Accesso remoto a Grafana con ngrok (opzionale)

La dashboard Grafana legge Prometheus sulla rete Docker, quindi per visualizzare i grafici da remoto basta il tunnel Grafana; la UI Prometheus non viene esposta. Grafana mantiene l’autenticazione (`admin` e `GRAFANA_ADMIN_PASSWORD`).

1. Nel dashboard ngrok recupera l’authtoken e il dominio HTTPS riservato. Nel file `.env` imposta `NGROK_AUTHTOKEN`, `NGROK_GRAFANA_DOMAIN` (solo host, ad esempio `nome.ngrok-free.app`) e `GRAFANA_ROOT_URL` (URL completo con slash finale, ad esempio `https://nome.ngrok-free.app/`). Usa lo stesso dominio per entrambe le variabili URL.
2. Avvia il tunnel:

   ```powershell
   docker compose --profile ngrok up -d ngrok-grafana
   docker compose logs -f ngrok-grafana
   ```

3. Apri il dominio configurato e accedi con l’utente `admin` e la password `GRAFANA_ADMIN_PASSWORD`. Il tunnel è pubblico su Internet: condividi il dominio solo con utenti autorizzati e mantieni una password robusta. Il tunnel disabilita l’ispezione delle richieste ngrok.

Arresta il tunnel con `docker compose --profile ngrok stop ngrok-grafana`. La porta Prometheus resta accessibile solo localmente; il tunnel ngrok non viene avviato dal normale `docker compose up`.

Per arrestare i container: `docker compose down`. Database, modelli FastEmbed, Qdrant e dati Prometheus/Grafana restano nei volumi Docker locali. `docker compose down -v` rimuove tutti questi volumi e cancella i dati.

## API e integrazioni

- API ticket interne: `main-app` applica identità e permessi; sono raggiungibili solo sulla rete Compose e richiedono un JWT firmato di breve durata.
- FastAPI: `/api/v1/help`, `/api/v1/rag/search`, API Admin documenti e MCP Streamable HTTP su `/mcp`.
- Agent copilot: `POST /api/v1/agent/tickets/{ticket_id}/copilot`, consentito solo ad Agent/Admin e subordinato all’autorizzazione MVC sul ticket.
- L’exporter Prometheus ascolta sulla porta container `8001`, non pubblicata sull’host; Prometheus ne raccoglie le metriche sulla rete Docker.
- La UI MVC richiede un token temporaneo via endpoint antiforgery-protected e lo mantiene solo in memoria nel browser.
- La chiamata interna Python→MVC usa HTTP sulla rete Docker non pubblicata, con JWT; è una semplificazione esclusiva della demo locale, non una configurazione per deployment condivisi.
- Con i default, ticket, estratti della knowledge base e query web **non vengono inviati** a OpenAI. Abilitando `OPENAI_TICKET_CONTEXT_ENABLED`, Help ticket e copilot inviano i campi autorizzati del ticket; il copilot non inoltra ID ticket, utente o assegnatario. `OPENAI_KNOWLEDGE_CONTEXT_ENABLED` abilita l’invio degli estratti documentali; `WEB_SEARCH_ENABLED` abilita l’invio della sola domanda a OpenAI web search. Le tre opzioni sono indipendenti e disattivate per default.
- Le richieste Responses usano `store=false`; ciò non equivale a una garanzia di zero retention del provider. Non abilitare l’invio di dati reali senza approvazione di privacy, policy, regione, retention e minimizzazione.
- Metriche e dashboard non registrano prompt, testo dei ticket, nomi, ID utente o ID ticket. Le metriche HTTP usano path template; gli access log Uvicorn sono disattivati, i logger HTTPX/HTTPcore e i log lifecycle HTTP MVC sono impostati a Warning (i warning e gli errori restano visibili). La ricerca ticket interna invia il testo nel body JSON, non nella query URL; lo smoke test ha verificato che il testo del body non compare nei log dei container. L’exporter è su una rete Docker interna dedicata. Prometheus e Grafana restano bindati a localhost; il profilo ngrok opzionale espone solo Grafana, che richiede login. Prometheus non ha autenticazione e non deve essere esposto direttamente.

## Test

```powershell
dotnet test main-app.Tests\main-app.Tests.csproj
Set-Location agentic-app
python -m pip install -r test-requirements.txt
python -m pytest
```

**Verifica locale corrente:** 3 test d’integrazione MVC e 23 test FastAPI superati, inclusi controlli di opt-in, minimizzazione dei campi ticket e metriche senza query o ID; Compose, scrape Prometheus e dashboard Grafana (12 pannelli) verificati. Lo smoke test locale ha confermato che la query inviata nel body non compare nei log dei container. Le chiamate di condivisione senza opt-in restituiscono HTTP 503 prima di recuperare ticket o chiamare OpenAI. Su 20 quesiti bilingui sintetici con una fonte attesa ciascuno, retrieval e reranking hanno ottenuto Recall@5 **1,00** e MRR@5 **0,975**: 19 fonti al primo posto e una al secondo (query sul laptop smarrito). Il solo RRF ha ottenuto MRR@5 **0,950**. È un benchmark dimostrativo, non una garanzia sul corpus del cliente. Le chiamate OpenAI live non sono state verificate: non è configurata una chiave e le condivisioni sono disabilitate.

Valutazione retrieval sui 20 quesiti bilingui inclusi (richiede i modelli e Qdrant configurato):

```powershell
python evaluate_retrieval.py
```

## Sviluppo Python senza Docker

Usa Python 3.12 e il virtual environment collegato ad [agentic-app](./agentic-app/README.md):

```powershell
Set-Location agentic-app
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -r test-requirements.txt
```

Avvia Qdrant dalla root con `docker compose up -d qdrant`; avvia MVC con `dotnet run --launch-profile https` da `main-app` e FastAPI con `.\run.ps1` da `agentic-app`. Per l’uso locale configura `AI_JWT_SIGNING_KEY`, `OPENAI_API_KEY` e `OPENAI_MODEL` nell’ambiente. `run.ps1` verifica il certificato MVC tramite il PEM locale; non disabilitare la verifica TLS.

## Limiti e sicurezza

- Compose pubblica le porte solo su `127.0.0.1`; certificati e segreti di sviluppo non sono adatti alla produzione.
- L’API ticket MVC rimane autorevole e applica i permessi requester/agent/admin. MCP non espone strumenti di scrittura.
- Gli utenti autenticati condividono l’indice documentale; implementare ACL per documento/tenant prima di caricare contenuti con permessi differenziati.
- L’AI può essere errata: verificare le citazioni e ogni suggerimento prima di agire.
- HTTPS protegge i due endpoint pubblici; il collegamento Python→MVC su HTTP è confinato alla rete Compose non pubblicata. Per ambienti condivisi servono TLS interno, gestione dei segreti, rete, logging e controlli operativi dedicati.

## Documenti

- [Piano di progetto in italiano](./plan.md)
- [Project plan in English](./plan-en.md)
- [README in English](./README-en.md)
