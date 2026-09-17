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

```text
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

```text
orthanc-dicommwl-broker/
├── orthanc-explorer-3-usable/   # OE3-Fork (Frontend, Git-Submodule)
├── mwl-broker/                  # FastAPI + pynetdicom Service
│   ├── mwl_broker/              # Package: api, dimse, db, metrics, echo
│   ├── tests/                   # pytest (API, Merge, DIMSE-Integration)
│   ├── scripts/cfind_smoke.py   # manueller C-FIND-Smoke-Test
│   └── Dockerfile
├── deploy/
│   ├── orthanc/orthanc.json     # Orthanc-Config (Credentials via env)
│   ├── oe3-stack.nginx.conf     # SPA + /orthanc-proxy + /broker-api
│   ├── oe3-config.js            # __OE3_CONFIG__ (orthancUrl, brokerUrl, flags)
│   └── postgres-init.sh         # erstellt DB `mwl`
├── docker-compose.yml           # Basis-Stack (produktionsfähig)
├── docker-compose.demo.yml      # Overlay: Mock-RIS ×2 + Peer-PACS
├── bootstrap.sh                 # Plug-and-play Ubuntu-Setup
└── .env.example                 # alle Ports/Credentials konfigurierbar
```

## Deployment / Konfiguration

- **`.env` steuert alles**: Ports, Bind-Adressen, AETs, Postgres-Credentials,
  Broker-Parameter (Echo-Intervall, Timeouts, erlaubte Calling-AETs, Strict-
  Store-Status, seen_items-Retention) und den JSON-Seed.
- **Isolation auf Multi-Projekt-Hosts**: `COMPOSE_PROJECT_NAME=mwl-broker`
  → eigene Container-Namen und eigenes Netzwerk; Postgres wird **nicht** auf
  dem Host exponiert; Orthanc-REST und Broker-API binden per Default an
  `127.0.0.1` (Zugriff über den OE3-nginx-Proxy, gleicher Origin → kein CORS).
- **Default-Ports 18xxx/14xxx** statt der üblichen 4242/8042 — der Referenz-
  Host belegt die Standardports bereits. `bootstrap.sh --check` meldet
  Kollisionen vor dem Start.
- **Orthanc-Config** in `deploy/orthanc/orthanc.json` (statische Optionen);
  Secrets über `ORTHANC__*` Env-Variablen aus `.env` (env überschreibt JSON).
- **Demo-Overlay** `docker-compose.demo.yml`: zwei Mock-RIS-SCPs (Variante b
  enthält absichtlich ein Duplikat → Dedupe-Demo) + zweites PACS (`PEER`) als
  Routing-Ziel. Seed setzt Quellen/Ziele automatisch.

## Verifikation (auf dem Referenz-Host durchgeführt)

| Check | Ergebnis |
|---|---|
| `docker compose config` (base + demo) | valide |
| Stack hochgefahren | alle Container healthy |
| C-FIND an `MWLBROKER:11113` | 3 gemergte Antworten aus 2 Quellen (Dedupe) |
| `seen_items` + `query_log` | geschrieben, PHI-frei (kein PatientName) |
| C-STORE `ACC-A-001` | per Regel ris-a → pacs-peer geroutet |
| C-STORE unbekannte Accession | Default-Target orthanc |
| C-ECHO-Matrix via `/api/v1/status` | alle Quellen/Ziele ok, RTT gemessen |
| OE3 via nginx | `/oe3/` UI, `/orthanc-proxy`, `/broker-api` |
| `pytest` | 15 Tests grün (inkl. DIMSE-Integration in-process) |
| `npm run test` / `tsc` / `lint` | 259 Tests, 0 Errors |
| Playwright Stack-E2E (Desktop 1280x800 + Mobile 375x812) | 8/8 grün, 0 Console-/Page-/Netzwerk-Fehler |

### Browser-Verifikation (Playwright, Chromium headless)

`e2e/stack/` im Frontend-Repo: `playwright.stack.config.ts` (Desktop- +
Mobile-Projekt; Basis-URL via `OE3_BASE` env, Default
`http://127.0.0.1:18082`) + `stack-viewport.spec.ts` (Study-Liste,
Broker-Dashboard, Echo-Button, Sidebar-Navigation, DOM-Analyse, Screenshots
pro Viewport unter `e2e/stack/screenshots/`).

### Ephemerer Test-Stack + lokale CI

`test-stack.sh` + `.env.test`: isolierte Stack-Kopie (Projekt `mwl-test`,
Ports `19xxx`/`14xxx`, eigene Volumes). Ablauf: `up -d --build` → Health-Wait
→ C-FIND-Smoke → Playwright (8 Tests) → `down -v`. Läuft parallel zum
regulären Stack auf dem geteilten Host und lässt keinen Zustand zurück.

`ci-local.sh` orchestriert die komplette lokale Pipeline gegen dieselbe
Code-Basis wie Produktion (gleiche Dockerfiles, gleiche `orthanc.json`):
backend pytest (15) → frontend tsc → lint → vitest (259) → docker-e2e
(8 Browser-Tests + DIMSE-Smoke). Verifiziert: alle Stages grün.
`--quick` überspringt die Docker-Stage.

Gefundene und behobene Defekte:

- **`/oe3-me` 404 → App komplett blockiert.** Der AuthGate ruft `/oe3-me`
  immer ab; ohne Backend-Proxy antwortete Orthanc 404 → "Zugriff
  verweigert". Fix: explizites Config-Opt-out `authCheck: false`
  (Default `true`, Prod-Verhalten unverändert) → lokale Admin-Session.
- **`GET /labels` → 404.** Korrekter Orthanc-Endpoint ist `/tools/labels`
  (Fork-Bug, betraf jedes Deployment).
- **Mobile Sidebar ohne `SheetTitle`** → Radix-A11y-Warnung in der Konsole.
  Fix: `sr-only` SheetHeader/Title/Description in `sidebar.tsx`.
- **Mobile Broker-Tabelle:** Endpoint-Zellen ohne Umbruch → Echo-Button
  abgeschnitten; RTT wrappte zweizeilig. Fix: `break-all` auf
  Endpoint-Zellen, `whitespace-nowrap` auf dem Echo-Badge,
  Echo-Button min. 36px Touch-Target auf Mobile.

## Phasen

| Phase | Umfang | Status |
|---|---|---|
| 1 | Broker-Scaffold: Config-API, MWL-Proxy, Store-Forwarding, Logs, Metriken | ✅ |
| 2 | Dev-Stack + Mock-RIS A/B + Smoke-Skript | ✅ |
| 3 | OE3: Broker-Dashboard read-only | ✅ |
| 4 | Plug-and-play: .env, orthanc.json, bootstrap.sh, Tests, Host-Verifikation | ✅ |
| 5 | OE3: Editoren für Quellen/Ziele/Regeln + Audit-Events | ☐ |
| 6 | Härtung: TLS, Retention-Job (seen_items), Alerting | ☐ |
| 7 | HL7-Adapter (ORM/ADT → lokale MWL-Quelle) | ☐ |

## Offene Punkte / Risiken

- **Charset** je Quelle testen (deutsche Namen, `ISO_IR 100` vs `ISO_IR 192`).
- **Dedupe-Strategie** muss fachlich bestätigt werden (gleicher Patient in
  zwei RIS? Accession-Kollisionen?).
- `seen_items` als Routing-Basis funktioniert nur, wenn die Worklist vorher
  abgefragt wurde — Fallback-Regel zwingend konfigurierbar.
- Orthanc kann parallel weiterhin Bilder direkt annehmen (Port 4242); der
  Broker-Port 11113 ist der empfohlene Eingang für Modalitäten.
