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
| OE3 UI | 18082 | http://host:18082/oe3/ |
| Orthanc REST | 18042 | nur `127.0.0.1` (`ORTHANC_HTTP_BIND`) |
| Orthanc DICOM | 14242 | AET `ORTHANC` |
| Broker REST + Metriken | 18081 | nur `127.0.0.1` (`BROKER_API_BIND`) |
| Broker DICOM | 11113 | AET `MWLBROKER` — **der Port für Modalitäten** |
| Postgres | — | intern, nicht exponiert |
| Mock-RIS A / B (demo) | 18114 / 18115 | |
| Peer-PACS (demo) | 18043 / 14243 | |

### Smoke-Tests

```bash
# C-FIND gegen den Broker (liefert gemergte Antworten der Mock-RIS):
python3 mwl-broker/scripts/cfind_smoke.py 127.0.0.1 11113 MWLBROKER

# Oder nach dem Boot im Browser: http://<host>:18082/oe3/ → "MWL Broker"
# zeigt Echo-Matrix, Zähler und das Live-Query-Log.
```

## Tests

```bash
cd mwl-broker && python -m pytest tests -q        # 15 Tests (API + DIMSE e2e)
cd orthanc-explorer-3-usable && npm run test      # 259 Tests
```

## Status

- [x] Architektur & Projektstruktur (README/project/agents)
- [x] mwl-broker: MWL-Proxy-SCP, Store-Routing, Config-API, Metriken, Echo-Monitoring
- [x] Dev-/Demo-Stack, .env-basierte Konfiguration, bootstrap.sh
- [x] OE3: `broker.ts` API-Client + Broker-Dashboard
- [x] Tests: 15 Backend (inkl. echter DIMSE-Integration), 10 Frontend neu
- [x] Verifiziert auf Zielhost: C-FIND-Fan-out, Dedupe, Store-Routing, Echo
- [ ] OE3: Editoren für Quellen/Ziele/Routing-Regeln
- [ ] Retention-Job für seen_items, Alerting, TLS am DIMSE
- [ ] HL7-ORM/ADT-Adapter (Worklist-Einträge ohne Upstream-C-FIND)
