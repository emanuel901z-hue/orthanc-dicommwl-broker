# agents.md — Konventionen für Coding-Agents in diesem Workspace

## Layout

- `orthanc-explorer-3-usable/` — Git-Repo (React SPA, OE3-Fork). Eigene
  Konventionen in `orthanc-explorer-3-usable/CLAUDE.md` — **dort gelten
  zusätzlich** dessen Regeln (Audit-Seam, PHI-safe Logging, Feature-Flags,
  `@/`-Alias, kein `console.log`, genau ein `<h1>` pro Page,
  `data-shortcut="search"` auf Suchfeldern).
- `mwl-broker/` — Python-Service (FastAPI + pynetdicom + SQLAlchemy).
- `ohif-viewer/` + `extension-radiology-advanced/` — gehärteter OHIF-v3.12.5-Build
  (Compose-Profil `viewer`); Regeln siehe unten.
- `deploy/` — `orthanc/orthanc.json`, `oe3-stack.nginx.conf`, `oe3-config.js`
  (OE3-Runtime-Config), `ohif-config.js` (OHIF-Runtime-Config), `postgres-init.sh`.
- `docker-compose.yml` (Workspace-Root) — Gesamtstack. Die
  `docker-compose.dev.yml` im Frontend-Repo ist nur für reine Frontend-
  Entwicklung gedacht.

## Commands

```bash
# Setup / Gesamtstack (Basis = produktionsfähig, Demo = + Mock-RIS + Peer)
./bootstrap.sh              # Docker-Check, .env anlegen, Port-Check, up -d
./bootstrap.sh --demo       # inkl. docker-compose.demo.yml
./bootstrap.sh --check      # nur Preflight
docker compose up -d --build
docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d

# Broker-Tests (ohne Docker; DIMSE-Tests nutzen ephemere Ports + sqlite)
cd mwl-broker && python -m pytest tests -q
# …mit Coverage (aktuell 96 %)
cd mwl-broker && .venv/bin/pytest tests -q --cov=mwl_broker --cov-report=term-missing

# Broker-API + Swagger/OpenAPI (laufender Stack)
curl -s http://127.0.0.1:18081/openapi.json | python3 -m json.tool | head
#   Swagger UI: http://127.0.0.1:18081/docs

# Broker lokal (Postgres via Docker, sonst BROKER_DATABASE_URL setzen)
cd mwl-broker && uvicorn mwl_broker.main:app --port 8081

# Frontend
cd orthanc-explorer-3-usable
npm install
npm run dev                 # Vite-Proxy: /orthanc-proxy, /broker-api
npm run test && npm run lint
npx tsc --noEmit -p tsconfig.app.json
npx vitest run --coverage    # Broker-UI-Coverage (aktuell 98,9 %)

# Deep-UI-Audit gegen den laufenden Stack (DOM-Checks + CRUD vs. REST-API,
# Desktop 1400x900 + Mobile 375x812, Screenshots in e2e/stack/shots/)
node e2e/stack/verify-ui.cjs

# Vollständige lokale Pipeline / Test-Stack / Fork-Push-Guard
./ci-local.sh               # pytest → tsc → lint → vitest → docker-e2e (--quick ohne Docker)
./test-stack.sh             # ephemerer Stack: up → DIMSE-Smokes → Playwright → down -v
./pre-push-fork.sh          # NUR so wird der OE3-Fork öffentlich gepusht (Audit + Secret-Scan)
```

**Push-Regel (zwei öffentliche Repos)**: Beide werden ausschließlich über
`./pre-push-fork.sh` gepusht — das Script prüft Outgoing-Commits/-Dateien
gegen eine Blacklist (.env, DBs, Keys, Screenshots, test-results, History-
Dateien), scannt den Diff auf Secret-Muster und verweigert Pushes an
Upstream-Remotes.

| Repo | Inhalt | Push |
|---|---|---|
| `orthanc-explorer-3-usable` | OE3-Fork: nur der UI-Slice | `./pre-push-fork.sh` |
| `orthanc-dicommwl-broker` | Broker-Service + Deployment + Docs (OE3 als Submodule) | `./pre-push-fork.sh --repo .` |

**Reihenfolge: erst Fork, dann Workspace.** Der Workspace pinnt den Fork als
Submodule — dessen Commit muss vorher auf dem öffentlichen Remote existieren,
sonst schlägt jeder Clone fehl.

Workspace-Interna (echte `.env`, Host-Ports, Krankenhaus-Topologie) gehören
grundsätzlich in kein öffentliches Repo; `.env.example`/`.env.test` sind
secret-freie Templates und per Allowlist erlaubt (bleiben secret-gescannt).

**Credentials**: Tokens stehen **nie** in Remote-URLs oder committeten Dateien.
Pro Repo ist ein repo-lokaler Credential-Helper gesetzt, der auf eine Datei
außerhalb des Repos zeigt (mode 600):

| Repo | Store-Datei | Config |
|---|---|---|
| Fork | `~/.config/git/credentials-oe3` | `git config --local credential.helper "store --file=…"` |
| Broker | `~/.config/git/credentials-broker` | dito |

Token rotieren = nur die Store-Datei neu schreiben:
`printf 'https://<user>:<token>@github.com\n' > ~/.config/git/credentials-broker && chmod 600 …`

## Regeln für den OHIF-Viewer (`ohif-viewer/`, `extension-radiology-advanced/`)

- **Build-Context ist das Repo-Root** (`context: .`, `dockerfile:
  ohif-viewer/Dockerfile`) — der Dockerfile kopiert zusätzlich
  `extension-radiology-advanced/`. Diese Extension hat (noch) kein Git-Remote,
  liegt deshalb als normaler Ordner im Repo; sobald sie ein Remote hat,
  kann sie als Submodule herausgezogen werden.
- **`ohif-viewer/default.js` ist generiert** (`build-config.js` aus
  `protocols/*.js` + `static-config.js`) → nicht editieren, nicht committen
  (steht in `.gitignore`). Änderungen an der App-Config gehören in
  `static-config.js` (Build-Default) bzw. `deploy/ohif-config.js` (Runtime).
- Der Viewer läuft hinter dem Compose-Profil **`viewer`** und wird über den
  OE3-nginx unter `/ohif/` ausgeliefert (Docker-DNS-Resolver pro Request,
  damit der Stack auch ohne Viewer startet). OE3 ruft ihn same-origin als
  `/ohif/viewer?StudyInstanceUIDs=…` auf.
- DICOMweb-Pfade zeigen auf `/orthanc-proxy/dicom-web` (mitgelieferter
  Orthanc). Die Carestream-Spezifika des Vorgängerprojekts (pacs-proxy,
  metadata-bridge, X-API-Key, Accession-Resolver) sind **nicht** Teil dieses
  Stacks — nicht wieder einführen.
- Das Image wird **nicht** in `test-stack.sh`/`ci-local.sh` gebaut (Build
  dauert 5-10 min). Änderungen am Viewer manuell verifizieren:
  `docker compose --profile viewer up -d --build ohif`.

## Deployment-Konventionen

- `.env` nie committen (steht in `.gitignore`); Änderungen an
  Konfigurations-Defaults immer in `.env.example` + README-Tabelle pflegen.
- Neue Host-Ports nur über `.env`-Variablen — auf dem Zielhost laufen andere
  Docker-Projekte, hartcodierte Standardports kollidieren.
- Postgres bleibt intern (kein `ports:`-Mapping); Orthanc-REST/Broker-API
  binden per Default an `127.0.0.1` — externer Zugriff läuft über den
  oe3-nginx-Proxy.
- Demo-Services (mock-ris, dicom-peer) gehören ausschließlich in
  `docker-compose.demo.yml`, nie in die Basis.

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
