# Projekt: DICOM-MWL-Broker für Orthanc

## Zielbild

Ein Krankenhaus betreibt Orthanc (+ Postgres-Index) und mehrere RIS/KIS-Systeme,
die jeweils eigene DICOM-MWL-Quellen (C-FIND SCPs) anbieten. Die Modalitäten
sollen **eine** Worklist-Anlaufstelle sehen. Der Broker:

1. **MWL-Proxy/Aggregator** — nimmt C-FIND (Modality Worklist Information
   Model FIND, SOP Class `1.2.840.10008.5.1.4.31`) von Modalitäten entgegen,
   fragt alle aktivierten Upstream-Quellen per C-FIND SCU ab, merged und
   dedupliziert die Antworten und liefert sie ans Gerät zurück.
2. **Store-Router** — nimmt Bilder per C-STORE entgegen, ordnet sie über
   Accession Number / SPS / StudyInstanceUID der ursprünglichen Worklist-Quelle
   zu und forwarded sie in das per Routing-Regel konfigurierte Ziel-PACS
   (oder nach Orthanc als Default/Archiv).
3. **Konfigurations-API** — REST-CRUD für Quellen, Ziele und Routing-Regeln,
   persistiert in Postgres (Schema `mwl` in der bestehenden Index-DB-Instanz).
4. **Monitoring** — Query-Log (wer fragte wann was), Store-/Forward-Log,
   periodisches C-ECHO auf alle Quellen/Ziele, Prometheus-Metriken, Health.
5. **OE3-UI** — der bestehende Orthanc-Explorer-Fork bekommt ein
   `broker`-Feature: Dashboard, Quellen-/Ziel-Editoren, Routing-Matrix,
   Live-Query-Log.

Nicht-Ziele (v1): MPPS, HL7-Listener, TLS am DIMSE (später via `tls-args`).

## Datenflüsse

```
 RIS_A (MWL SCP) ──┐                          ┌──> PACS_KH (C-STORE)
 RIS_B (MWL SCP) ──┤   C-FIND   ┌──────────┐  │
 KIS   (MWL SCP) ──┼───────────>│ mwl-     │──┼──> PACS_ANDERES
                   │   SCU      │ broker   │  │
  MRT/CT ── C-FIND ─────────────>│  :11113  │  └──> Orthanc (Default)
         <── pending answers ────│          │       (Index in Postgres)
  MRT/CT ── C-STORE ────────────>│          │──┐
                                 └──────────┘  │ Routing via seen_items
            OE3 UI ── REST ──────> :8081/api   │
            Prometheus ── pull ──> :8081/metrics
```

### C-FIND-Flow

1. Modality assoziiert gegen `MWLBROKER:11113` (AET konfigurierbar).
2. Handler liest `event.identifier`, setzt je Quelle `SpecificCharacterSet`
   (Quellen-Config, Default `ISO_IR 100` — Umlaute!).
3. Pro Quelle (parallel, je mit eigenem Timeout): C-FIND SCU mit dem
   `calling_aet` aus der Quellen-Config — manche RIS liefern nur an bekannte AEs.
4. Merge + Dedupe über `(PatientID, AccessionNumber, SPS-ID)`; Quelle der
   ersten Antwort gewinnt. Pro Treffer: Eintrag in `seen_items`
   (AccessionNumber, SPS-ID, StudyInstanceUID, source_id, ts) — Basis für
   Store-Routing.
5. `0xFF00`-Answers streamen zurück; `0x0000` am Ende. Alles ins `query_log`.

### C-STORE-Flow

1. `evt.dataset` lesen, `file_meta` übernehmen.
2. Lookup `seen_items` (Accession → SPS → StudyUID, in der Reihenfolge) →
   `source_id` → aktive Routing-Regel → `pacs_target`. Kein Match → Default-
   Target (Orthanc).
3. SCU-Forward `send_c_store`; Ergebnis + Fehler ins `store_log`; Metrik.
4. Status an Modality: 0x0000 bei Erfolg, 0xA7xx/0xCxxx bei Forward-Fehler
   (konfigurierbar: streng vs. best-effort).

## DB-Schema (`mwl`, eigene Datenbank auf der shared Postgres)

| Tabelle | Inhalt |
|---|---|
| `mwl_source` | name, aet (called), host, port, calling_aet, charset, enabled, timeout_s, priority |
| `pacs_target` | name, aet, host, port, calling_aet, enabled, is_default |
| `routing_rule` | source_id → target_id, priority, enabled |
| `seen_item` | accession, sps_id, study_uid, source_id, ts (Retention: purge > N Tage) |
| `query_log` | ts, calling_aet, query_keys (JSON, **kein PatientName**), answers, per_source (JSON), duration_ms, status |
| `store_log` | ts, calling_aet, sop_instance_uid, study_uid, accession, source_id, target_id, status, error |

PHI-Leitlinie: `PatientName` nie in Logs; `PatientID` nur wo für Matching nötig
(`seen_item` optional), Retention-Job räumt auf.

## REST-API (`/api/v1`)

- `GET/POST/PUT/DELETE /sources`, `POST /sources/{id}/echo`
- `GET/POST/PUT/DELETE /targets`, `POST /targets/{id}/echo`
- `GET/POST/PUT/DELETE /rules`
- `GET /logs/queries`, `GET /logs/stores` (paged, Filter: aet, source, status, since)
- `GET /status` — SCP-Listener, Echo-Matrix (Quellen+Ziele), Zähler
- `GET /healthz`, `GET /metrics` (Prometheus)

## Metriken

- `mwl_cfind_requests_total{result}`, `mwl_cfind_duration_seconds` (Histogram)
- `mwl_cfind_upstream_answers_total{source}`
- `mwl_cstore_total{target,status}`
- `mwl_echo_up{kind,name}` (Gauge, Echo-Loop)
- `mwl_seen_items` (Gauge)

## OE3-Frontend

- `src/api/broker.ts` — `brokerFetch` (Base-URL `config.brokerUrl`), typed API
- `src/config/runtime.ts` — optionales `brokerUrl` im `__OE3_CONFIG__`
- Feature-Flag `mwlBroker` (Alias `enableMwlBroker`)
- `src/features/broker/` — Dashboard (Status + Echo-Matrix + Live-Query-Log);
  später: Source/Target-Editoren, Routing-Matrix
- Route `/broker`, Sidebar-Eintrag, i18n (en/de; Rest per fallbackLng)

## Repo-Layout

```
orthanc-dicommwl-broker/
├── orthanc-explorer-3-usable/   # OE3-Fork (Frontend, eigenes Git-Repo)
├── mwl-broker/                  # FastAPI + pynetdicom Service
│   ├── mwl_broker/              # Package: api, dimse, db, metrics, echo
│   ├── tests/                   # pytest (API + Merge-Logik)
│   ├── scripts/cfind_smoke.py   # manueller C-FIND-Smoke-Test
│   └── Dockerfile
├── deploy/postgres-init.sh      # erstellt DB `mwl`
└── docker-compose.yml           # Gesamtstack
```

## Phasen

| Phase | Umfang | Status |
|---|---|---|
| 1 | Broker-Scaffold: Config-API, MWL-Proxy, Store-Forwarding, Logs, Metriken | ✅ |
| 2 | Dev-Stack + Mock-RIS A/B + Smoke-Skript | ✅ |
| 3 | OE3: Broker-Dashboard read-only | ✅ |
| 4 | OE3: Editoren für Quellen/Ziele/Regeln + Audit-Events | ☐ |
| 5 | Härtung: TLS, Allowed-Calling-AETs, Retention-Job, Alerting | ☐ |
| 6 | HL7-Adapter (ORM/ADT → lokale MWL-Quelle) | ☐ |

## Offene Punkte / Risiken

- **Charset** je Quelle testen (deutsche Namen, `ISO_IR 100` vs `ISO_IR 192`).
- **Dedupe-Strategie** muss fachlich bestätigt werden (gleicher Patient in
  zwei RIS? Accession-Kollisionen?).
- `seen_items` als Routing-Basis funktioniert nur, wenn die Worklist vorher
  abgefragt wurde — Fallback-Regel zwingend konfigurierbar.
- Orthanc kann parallel weiterhin Bilder direkt annehmen (Port 4242); der
  Broker-Port 11113 ist der empfohlene Eingang für Modalitäten.
