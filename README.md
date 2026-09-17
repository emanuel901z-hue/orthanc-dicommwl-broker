# orthanc-dicommwl-broker

Workspace für einen **DICOM Modality-Worklist-Broker** mit sauberem Konfigurations-
Interface und Monitoring, aufgebaut auf:

| Komponente | Pfad | Zweck |
|---|---|---|
| `orthanc-explorer-3-usable/` | Frontend (Submodule) | OE3-Fork (React SPA) — Konfigurations- und Monitoring-UI für den Broker |
| `mwl-broker/` | Backend | Python-Service (FastAPI + pynetdicom): MWL-SCP (C-FIND-Proxy/Aggregator), C-STORE-SCP mit Quellen-Routing, Config-API, Query-/Store-Log, Prometheus-Metriken |
| `docker-compose.yml` | Stack | Orthanc + Postgres-Index + Broker + OE3 (produktionsfähige Basis) |
| `docker-compose.demo.yml` | Overlay | Zwei Mock-RIS-Quellen + zweites PACS zum Testen des Routings |
| `bootstrap.sh` | Setup | Plug-and-play-Installer für Ubuntu Server |
| `.env.example` | Config | Alle Ports/Credentials — nach `.env` kopieren |

## Konzept in einem Satz

Die Modalitäten im Krankenhaus sprechen ausschließlich mit dem Broker. Für
C-FIND-MWL tut der Broker gegenüber dem Gerät so, als wäre er die eine Worklist-
Quelle — intern fragt er aber **mehrere** Upstream-Systeme (RIS/KIS) ab, merged
und dedupliziert die Antworten. Eingehende Bilder nimmt der Broker per C-STORE
entgegen und routet sie je nach Worklist-Herkunft ins richtige PACS (oder nach
Orthanc als Index/Archiv).

Details zur Architektur: [`project.md`](project.md)
Konventionen für Coding-Agents: [`agents.md`](agents.md)

## Quickstart (Ubuntu Server, Plug-and-play)

```bash
git clone --recurse-submodules <repo-url> orthanc-dicommwl-broker
cd orthanc-dicommwl-broker
./bootstrap.sh            # prüft Docker, .env, Port-Kollisionen; startet Stack
./bootstrap.sh --demo     # inkl. Mock-RIS-Quellen + zweitem PACS
./bootstrap.sh --check    # nur Preflight, startet nichts
```

`bootstrap.sh` installiert Docker falls nötig, legt `.env` aus
`.env.example` an, warnt bei Port-Kollisionen (wichtig auf Hosts mit anderen
Docker-Projekten) und wartet auf die Healthchecks.

### Default-Ports (in `.env` anpassbar)

Der Referenz-Host belegt die üblichen DICOM-Ports bereits — deshalb liegen
die Defaults auf freien Ports:

| Service | Host-Port | Bemerkung |
|---|---|---|
| OE3 UI | 18082 | `http://host:18082/oe3/` |
| Orthanc REST | 18042 | nur `127.0.0.1` (`ORTHANC_HTTP_BIND`) |
| Orthanc DICOM | 14242 | AET `ORTHANC` |
| Broker REST + Metriken | 18081 | nur `127.0.0.1` (`BROKER_API_BIND`) |
| Broker DICOM | 11113 | AET `MWLBROKER` — **der Port für Modalitäten** |
| Postgres | — | intern, nicht exponiert |
| Mock-RIS A / B (demo) | 18114 / 18115 | |
| Peer-PACS (demo) | 18043 / 14243 | |
| OHIF Viewer | 18083 | optional (`--profile viewer`), nur `127.0.0.1` — OE3 nutzt `/ohif/` über den Proxy |

### OHIF-Viewer (optional)

Der gehärtete OHIF v3.12.5-Build (`ohif-viewer/`) inklusive der eigenen
Extension-Panels (`extension-radiology-advanced/`) ist als Compose-Profil
angebunden. Er läuft **same-origin** unter `/ohif/` hinter dem OE3-nginx —
damit funktioniert der „In OHIF öffnen"-Button der Studienansicht direkt,
und DICOMweb kommt aus dem mitgelieferten Orthanc (`/orthanc-proxy/dicom-web`).

```bash
# baut OHIF aus dem Quelltext (Clone + Install + Build, ~5-10 min beim ersten Mal)
docker compose --profile viewer up -d --build ohif
# oder beim Bootstrap: ./bootstrap.sh --viewer

# Aufruf:  http://<host>:18082/ohif/viewer?StudyInstanceUIDs=<UID>
#          bzw. aus OE3 heraus über den Button in der Studienansicht
```

Die Viewer-Config liegt in `deploy/ohif-config.js` (ins Image gemountet,
änderbar ohne Rebuild). Ohne das Profil startet der Stack unverändert —
`/ohif/` liefert dann nur einen Fehler.

### Smoke-Tests

```bash
# C-FIND gegen den Broker (liefert gemergte Antworten der Mock-RIS):
python3 mwl-broker/scripts/cfind_smoke.py 127.0.0.1 11113 MWLBROKER

# Oder nach dem Boot im Browser: http://<host>:18082/oe3/ → "MWL Broker"
# zeigt Echo-Matrix, Zähler und das Live-Query-Log.
```

## Tests

```bash
cd mwl-broker && python -m pytest tests -q        # 88 Tests (API + DIMSE e2e + Transforms/Settings)
cd orthanc-explorer-3-usable && npm run test      # 325 Tests

# Browser-E2E gegen den laufenden Stack (Chromium headless, Desktop 1280x800
# + Mobile 375x812; DOM-Analyse, Console-/Page-Errors, Screenshots):
cd orthanc-explorer-3-usable
npx playwright test --config=e2e/stack/playwright.stack.config.ts
# Screenshots + DOM-Reports: e2e/stack/screenshots/

# Ephermerer Test-Stack (eigener Projektname "mwl-test", Ports 19xxx/14xxx,
# läuft parallel zum regulären Stack; up → C-FIND-Smoke → Playwright → down -v):
./test-stack.sh          # alles; --keep lässt ihn laufen, --down räumt ab

# Coverage (Broker-Code): backend 96 %, frontend Broker-UI 98.9 %
cd mwl-broker && .venv/bin/pytest tests -q --cov=mwl_broker --cov-report=term-missing
cd orthanc-explorer-3-usable && npx vitest run --coverage

# Lokale CI-Pipeline (alle Stages: backend pytest → tsc → lint → vitest →
# docker-e2e auf dem Test-Stack; gleiche Images/Code-Basis wie Produktion):
./ci-local.sh            # alles; --quick ohne Docker-Stage

# Optionaler pre-push-Hook (Quick-Stages lokal, da CI nur bei PRs läuft):
git config core.hooksPath .githooks

# Push-Guard für beide öffentlichen Repos (Blacklist + Secret-Scan +
# Upstream-Schutz) — nur so wird gepusht, Reihenfolge: erst Fork, dann Workspace:
./pre-push-fork.sh --dry-run            # OE3-Fork (orthanc-explorer-3-usable)
./pre-push-fork.sh --repo . --dry-run   # Broker-Workspace (dieses Repo)
```

GitHub-CI (`.github/workflows/ci.yml`) läuft als PR-Gate auf `main`/`develop`
sowie manuell: pytest, lint+tsc+vitest, Docker-E2E-Stack, audit-ci+pip-audit,
Gitleaks, Semgrep-SAST, Trivy-Container-Scan, License-Check, Markdownlint.
Privates OE3-Submodule benötigt Secret `SUBMODULE_PAT` (read access).

## Status

- [x] Architektur & Projektstruktur (README/project/agents)
- [x] mwl-broker: MWL-Proxy-SCP, Store-Routing, Config-API, Metriken, Echo-Monitoring
- [x] Dev-/Demo-Stack, .env-basierte Konfiguration, bootstrap.sh
- [x] OE3: `broker.ts` API-Client + Broker-Dashboard
- [x] Tests: 60 Backend, 45 Frontend neu (inkl. Konfig-UI + Audit-Vertrag)
- [x] Verifiziert auf Zielhost: C-FIND-Fan-out, Dedupe, Store-Routing, Echo
- [x] Browser-E2E (Playwright, Desktop+Mobile): 22/22 grün, 0 Console-Errors
- [x] OE3: vollständige Konfigurations-UI — Quellen, Ziele, Routing-Regeln,
      Modify-Regeln (DICOM-Tag-Transformationen), Laufzeit-Settings (Audit-Events)
- [x] Retention-Purge für seen_items (Settings-gesteuert)
- [ ] Nächste Ausbaustufen: siehe [docs/roadmap-worklist-broker.md](docs/roadmap-worklist-broker.md)
      (P0: Worklist-Cache mit Stale-Fallback, C-STORE-Spool mit Retry,
      Circuit Breaker; P1: Config-Audit/Export/Rollback, Simulation,
      Health-Panel, Alerting)
- [ ] HL7-ORM/ADT-Adapter (Worklist-Einträge ohne Upstream-C-FIND)
