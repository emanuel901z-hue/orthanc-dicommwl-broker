# agents.md — Konventionen für Coding-Agents in diesem Workspace

## Layout

- `orthanc-explorer-3-usable/` — Git-Repo (React SPA, OE3-Fork). Eigene
  Konventionen in `orthanc-explorer-3-usable/CLAUDE.md` — **dort gelten
  zusätzlich** dessen Regeln (Audit-Seam, PHI-safe Logging, Feature-Flags,
  `@/`-Alias, kein `console.log`, genau ein `<h1>` pro Page,
  `data-shortcut="search"` auf Suchfeldern).
- `mwl-broker/` — Python-Service (FastAPI + pynetdicom + SQLAlchemy).
- `deploy/` — Postgres-Init, zukünftig weitere Deployment-Artefakte.
- `docker-compose.yml` (Workspace-Root) — Gesamtstack. Die
  `docker-compose.dev.yml` im Frontend-Repo ist nur für reine Frontend-
  Entwicklung gedacht.

## Commands

```bash
# Gesamtstack
docker compose up -d --build

# Broker-Tests (ohne Docker, nutzt SQLite-freie Unit-Tests)
cd mwl-broker && python -m pytest tests -q

# Broker lokal (Postgres via Docker, sonst DATABASE_URL setzen)
cd mwl-broker && uvicorn mwl_broker.main:app --port 8081

# Frontend
cd orthanc-explorer-3-usable
npm install
npm run dev                 # Vite-Proxy: /orthanc-proxy, /broker-api
npm run test && npm run lint
npx tsc --noEmit -p tsconfig.app.json
```

## Regeln für den Broker (`mwl-broker/`)

- **PHI**: `PatientName` niemals in Logs/Metriken/DB-Logs. Erlaubt für
  Matching: AccessionNumber, SPS-ID, StudyInstanceUID. PatientID nur in
  `seen_items` mit Retention.
- **DIMSE-Threads**: pynetdicom-Handler laufen in eigenen Threads — kein
  asyncio dort; DB-Zugriff über normale SQLAlchemy-Sessions (pro Aufruf
  öffnen/schließen). FastAPI-Endpunkte sind sync `def` (Threadpool).
- **Keine blockierenden Upstream-Calls ohne Timeout** — jede Quelle hat
  `timeout_s`; ein toter RIS darf die Antwort an die Modality nicht verzögern.
- **SpecificCharacterSet** je Quelle aus Config setzen (Default `ISO_IR 100`).
- Metriken nur über `metrics.py` — keine ad-hoc-Prometheus-Clients.

## Regeln für das Frontend

- Neuer Broker-Code lebt in `src/features/broker/` + `src/api/broker.ts`.
- Broker-Requests gehen über `brokerFetch` (Base = `config.brokerUrl`), **nicht**
  über `orthancFetch` — andere Fehlerbehandlung, kein healthTracker-Reset für
  Orthanc.
- Feature-Flag `mwlBroker` (Alias `enableMwlBroker`) — ohne `brokerUrl` in
  `config.js` bleibt das Feature unsichtbar.
- Schreiboperationen am Broker (Sources/Targets/Rules ändern) emittieren
  BEFORE+AFTER Audit-Events wie jeder andere Write (siehe `src/actions/`).

## Definition of Done

- `pytest` grün in `mwl-broker/`, `npm run test` + `tsc --noEmit` grün im
  Frontend.
- Keine Secrets/Credentials in Dateien — Dev-Credentials bleiben Dev
  (`dev`/`dev`), Produktion via Env.
- Compose-Services haben Healthchecks; Logging-Limits wie im bestehenden
  Compose (`json-file`, max-size).
