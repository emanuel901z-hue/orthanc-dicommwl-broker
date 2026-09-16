# orthanc-dicommwl-broker

Workspace für einen **DICOM Modality-Worklist-Broker** mit sauberem Konfigurations-
Interface und Monitoring, aufgebaut auf:

| Komponente | Pfad | Zweck |
|---|---|---|
| `orthanc-explorer-3-usable/` | Frontend | OE3-Fork (React SPA) — dient als Konfigurations- und Monitoring-UI für den Broker |
| `mwl-broker/` | Backend | Python-Service (FastAPI + pynetdicom): MWL-SCP (C-FIND-Proxy/Aggregator), C-STORE-SCP mit Quellen-Routing, Config-API, Query-/Store-Log, Prometheus-Metriken |
| `docker-compose.yml` | Stack | Orthanc + Postgres-Index + Broker + OE3 + zwei Mock-RIS-Quellen |

## Konzept in einem Satz

Die Modalitäten im Krankenhaus sprechen ausschließlich mit dem Broker. Für
C-FIND-MWL tut der Broker gegenüber dem Gerät so, als wäre er die eine Worklist-
Quelle — intern fragt er aber **mehrere** Upstream-Systeme (RIS/KIS) ab, merged
und dedupliziert die Antworten. Eingehende Bilder nimmt der Broker per C-STORE
entgegen und routet sie je nach Worklist-Herkunft ins richtige PACS (oder nach
Orthanc als Index/Archiv).

Details zur Architektur: [`project.md`](project.md)
Konventionen für Coding-Agents: [`agents.md`](agents.md)

## Quickstart (Dev-Stack)

```bash
docker compose up -d --build
```

| Service | Endpoint |
|---|---|
| OE3 UI | http://localhost:8082/oe3/ |
| Orthanc REST | http://localhost:8042 |
| Broker REST-API | http://localhost:8081/api/v1 (`/docs` = OpenAPI) |
| Broker Metrics | http://localhost:8081/metrics |
| Orthanc DICOM | AET `ORTHANC`, Port 4242 |
| Broker DICOM | AET `MWLBROKER`, Port 11113 (MWL C-FIND + C-STORE) |
| Mock-RIS A | AET `RIS_A`, Port 11114 |
| Mock-RIS B | AET `RIS_B`, Port 11115 |

Smoke-Test von außen (C-FIND gegen den Broker):

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install pynetdicom pydicom
python mwl-broker/scripts/cfind_smoke.py   # fragt Broker auf 127.0.0.1:11113 ab
```

## Status

- [x] Architektur & Projektstruktur (README/project/agents)
- [x] mwl-broker Scaffold: MWL-Proxy-SCP, Store-Routing, Config-API, Metriken
- [x] Dev-Stack mit 2 Mock-RIS-Quellen
- [x] OE3: `broker.ts` API-Client + Broker-Dashboard
- [ ] OE3: Editoren für Quellen/Ziele/Routing-Regeln
- [ ] HL7-ORM/ADT-Adapter (Worklist-Einträge ohne Upstream-C-FIND)
- [ ] Alerting (Webhook bei Source-/Target-Ausfall)
