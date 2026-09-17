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
- `GET/POST/PUT/DELETE /transforms` — Modify-Regeln; `operations` werden gegen
  das DICOM-Datenlexikon validiert (unbekanntes Keyword → 422 mit Detail-Liste),
  SOP/Study/Series-UIDs sind gesperrt (PACS-Linkage)
- `GET /settings` — effektiver Wert + ENV-Default + Quelle (`db`|`env`);
  `PUT /settings/{key}` (Override, typvalidiert), `DELETE /settings/{key}` (Reset)
- `GET /logs/queries`, `GET /logs/stores` (paged, Filter: aet, source, status, since)
- `GET /status` — SCP-Listener, Echo-Matrix (Quellen+Ziele), Zähler
- `GET /healthz`, `GET /metrics` (Prometheus)

### Modify-Regeln (Tag-Transformation beim Weiterleiten)

`transform_rule`-Tabelle: Name, Scope (`source_id`/`target_id`, NULL = beliebig),
Priorität, `operations` (JSON). Angewendet im C-STORE-Pfad **vor** dem Forward:

| Op | Wirkung |
|---|---|
| `set` | Tag auf Wert setzen (pydicom konvertiert per VR) |
| `remove` | Tag entfernen |
| `prefix` / `suffix` | bestehenden Wert umrahmen |
| `replace` | Regex-Ersetzung im bestehenden Wert |
| `copy` | Wert eines anderen Tags übernehmen |

Fehlertoleranz: eine fehlschlagende Operation wird geloggt und übersprungen —
die Instanz wird trotzdem weitergeleitet. Die angewendeten Regelnamen landen
im `store_log.applied_transforms` (Audit-Trail). Validierung gegen
`pydicom.datadict`; UID-Tags sind gesperrt.

### OHIF-Viewer (optional, Compose-Profil `viewer`)

Der gehärtete OHIF-v3.12.5-Build aus dem Vorgängerprojekt ist angebunden:

- **Build-Context ist das Repo-Root**, weil der Dockerfile neben
  `ohif-viewer/` auch `extension-radiology-advanced/` kopiert (Extension
  wird per `pluginConfig.json` mit `default: true` registriert und liefert
  u.a. PACS-Browser, TIC, Mismatch, Vessel Tracking, ROI-Statistik,
  Tag-Browser, Cine, MPR/Slab-Steuerung).
- **Build-Patches** (`ohif-viewer/patch-*.js`) härten SR-Bulkdata,
  Encapsulated-PDF-Frames, VTK-Shader-Nulls, Dynamic-Volume-Metadaten und
  den StudyBrowser; `check-patches.js` verifiziert sie nach dem Build.
- **Auslieferung same-origin**: Der OE3-nginx proxied `/ohif/` auf den
  Viewer-Container (Docker-DNS-Resolver pro Request → der Stack startet auch
  ohne laufenden Viewer). Damit funktioniert OE3s „In OHIF öffnen" direkt
  (`/ohif/viewer?StudyInstanceUIDs=…`).
- **DICOMweb** kommt aus dem mitgelieferten Orthanc über
  `/orthanc-proxy/dicom-web` — kein pacs-proxy, keine metadata-bridge,
  kein API-Key nötig (die Carestream-Spezifika des Vorgängerprojekts
  entfallen).
- **Config zur Laufzeit**: `deploy/ohif-config.js` wird über die im Image
  eingebaute `config/default.js` gemountet — Änderungen brauchen keinen
  Rebuild. `ohif-viewer/default.js` ist ein generiertes Artefakt
  (`build-config.js` aus `protocols/` + `static-config.js`) und wird nicht
  versioniert.

**Verifiziert** (Image `mwl-broker-ohif`, Stack mit Demo-Overlay):

| Check | Ergebnis |
|---|---|
| Image-Build | erfolgreich (83 Hanging Protocols assemblieren, alle Build-Patches applied) |
| Auslieferung | `http://host:18082/ohif/` → 200 über den OE3-nginx (direkt: 18083) |
| Asset-Pfade | `/ohif/...` (`PUBLIC_URL=/ohif/` im Dockerfile) |
| Runtime-Config | gemountete `deploy/ohif-config.js` aktiv (`Orthanc DICOMweb`, `/orthanc-proxy/dicom-web`) |
| Studie laden | Metadaten + Bildabruf über DICOMweb, alle Requests 200 |
| Rendering | Canvas gerendert, W/L aus Pixeldaten (W 1772 / L 1086), **0 Console-Errors** |

Hinweis: Der Viewer braucht Instanzen **mit PixelData** — die synthetischen
C-STORE-Smoke-Instanzen (nur zum Routing-Test) liefern bei WADO-RS 400.

**Panel-Umfang (entschieden)**: Der Dockerfile patcht 7 der 12 von der
Extension registrierten Panels in die Mode-Layouts (`dicomTagBrowserPanel`,
`hotkeyHelpPanel`, `measurementExportPanel`, `mprSlabPanel`, `roiStatsPanel`,
`studyComparePanel`, `wlPresetsPanel`). Bewusst **nicht** im Layout:
`pacsBrowserPanel`, `cineNavPanel`, `ticPanel`, `mismatchPanel`,
`vesselTrackingPanel` — sie sind im Bundle vorhanden, erscheinen aber nicht
als Tabs. Zum Aktivieren die Namen in der `panelNames`-Liste des Dockerfiles
ergänzen und neu bauen (der ältere Stand hatte alle 12).

**OE3-Anbindung**: OE3s „In OHIF öffnen" ruft vorher
`POST /api/v1/pacs/viewer-session` (Backend-Proxy-Endpoint). In diesem Stack
existiert der nicht — deshalb setzt `deploy/oe3-config.js` `viewerSession:
false`; der Klick öffnet den Viewer direkt (verifiziert: 0 Calls, neuer Tab
mit `/ohif/viewer?StudyInstanceUIDs=…`).

### Laufzeit-Settings (ENV-Default + DB-Override)

`broker_setting`-Tabelle (Key/Value). Auflösung: DB-Wert schlägt ENV,
`DELETE /settings/{key}` fällt auf ENV zurück. Gültige Keys:
`allowed_calling_aets`, `strict_store_status`, `seen_item_ttl_days`,
`echo_interval_s`. Die DIMSE-Handler und der Echo-Loop lesen die effektiven
Werte zur Laufzeit → Änderungen wirken ohne Container-Neustart. Der
Echo-Loop führt zusätzlich stündlich den `seen_items`-Retention-Purge aus.

**OpenAPI/Swagger**: vollständig dokumentiert — App-Description, Tags
(sources/targets/rules/logs/monitoring), Summary + Response-Description pro
Endpoint, Query-Param- und Schema-Feld-Descriptions. Spec unter
`/openapi.json`, UI unter `/docs`. Ein Regressionstest
(`test_openapi_documents_all_endpoints`) erzwingt Summary/Tag für jeden
Endpoint und Descriptions für die Kern-Schemas.

## Metriken

- `mwl_cfind_requests_total{result}`, `mwl_cfind_duration_seconds` (Histogram)
- `mwl_cfind_upstream_answers_total{source}`
- `mwl_cstore_total{target,status}`
- `mwl_echo_up{kind,name}` (Gauge, Echo-Loop)
- `mwl_seen_items` (Gauge)

## OE3-Frontend

- `src/api/broker.ts` — `brokerFetch` (Base-URL `config.brokerUrl`), typed API
  inkl. Transforms + Settings; 404/409/422-Details werden durchgereicht
  (Konfigurationsmeldungen, PHI-frei), alle anderen Status bleiben gescrubbt
- `src/config/runtime.ts` — optionales `brokerUrl` im `__OE3_CONFIG__`
- Feature-Flag `mwlBroker` (Alias `enableMwlBroker`)
- `src/features/broker/` — **komplette Konfigurationsoberfläche**:
  - `pages/BrokerPage` — Monitoring (Status, Echo-Matrix, Live-Query-Log)
  - `pages/SourcesPage` — Upstream-Quellen CRUD (+ Enable, C-ECHO)
  - `pages/TargetsPage` — Store-Ziele CRUD (+ Default, C-ECHO)
  - `pages/RulesPage` — Routing-Regeln (Quelle → Ziel, Priorität, Toggle)
  - `pages/TransformsPage` — Modify-Regeln (Tag-Operationen, Scope, Priorität)
  - `pages/BrokerSettingsPage` — Laufzeit-Settings (ENV-Default + Override/Reset)
  - `hooks/use-broker-writes` — auditierte Writes (BEFORE+AFTER, wie `src/actions/`)
- Routen `/broker{,/sources,/targets,/rules,/transforms,/settings}` als
  Sidebar-Untergruppe; i18n en/de (Rest per fallbackLng)

## Repo-Layout

```text
orthanc-dicommwl-broker/
├── orthanc-explorer-3-usable/   # OE3-Fork (Frontend, Git-Submodule)
├── mwl-broker/                  # FastAPI + pynetdicom Service
│   ├── mwl_broker/              # Package: api, dimse, db, metrics, echo
│   ├── tests/                   # pytest (API, Merge, DIMSE-Integration)
│   ├── scripts/cfind_smoke.py   # manueller C-FIND-Smoke-Test
│   └── Dockerfile
├── ohif-viewer/                 # gehärteter OHIF-v3.12.5-Build (Dockerfile + Patches)
│   ├── Dockerfile               # Multi-Stage: OHIF-Clone + Patches → nginx
│   ├── static-config.js         # App-Config (DICOMweb-Root, routerBasename /ohif/)
│   ├── protocols/*.js           # modulare Hanging Protocols → default.js
│   ├── patch-*.js               # Build-Patches (SR, PDF, VTK, StudyBrowser, …)
│   └── viewer-nginx.conf        # Container-interner nginx (Port 8080)
├── extension-radiology-advanced/ # eigene OHIF-Extension (12 Panels, Hanging Protocols)
├── deploy/
│   ├── orthanc/orthanc.json     # Orthanc-Config (Credentials via env)
│   ├── oe3-stack.nginx.conf     # SPA + /orthanc-proxy + /broker-api + /ohif
│   ├── oe3-config.js            # __OE3_CONFIG__ (orthancUrl, brokerUrl, flags)
│   ├── ohif-config.js           # OHIF-Runtime-Config (gemountet, ohne Rebuild änderbar)
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
| `pytest` | 60 Tests grün (inkl. DIMSE-Integration in-process) |
| `npm run test` / `tsc` / `lint` | 298 Tests, 0 Errors |
| Playwright Stack-E2E (Desktop 1280x800 + Mobile 375x812) | 22/22 grün, 0 Console-/Page-/Netzwerk-Fehler |

### Browser-Verifikation (Playwright, Chromium headless)

`e2e/stack/` im Frontend-Repo: `playwright.stack.config.ts` (Desktop- +
Mobile-Projekt; Basis-URL via `OE3_BASE` env, Default
`http://127.0.0.1:18082`) + `stack-viewport.spec.ts` (Study-Liste,
Broker-Dashboard, Echo-Button, Sidebar-Navigation, DOM-Analyse, Screenshots
pro Viewport unter `e2e/stack/screenshots/`).

### Ephemerer Test-Stack + lokale CI

`test-stack.sh` + `.env.test`: isolierte Stack-Kopie (Projekt `mwl-test`,
Ports `19xxx`/`14xxx`, eigene Volumes). Ablauf: `up -d --build` → Health-Wait
→ C-FIND-Smoke → C-FIND-Smoke → C-STORE-Routing-Check (Regel→Peer, Default→Orthanc) → Playwright (22 Tests) → `down -v`. Läuft parallel zum
regulären Stack auf dem geteilten Host und lässt keinen Zustand zurück.

`ci-local.sh` orchestriert die komplette lokale Pipeline gegen dieselbe
Code-Basis wie Produktion (gleiche Dockerfiles, gleiche `orthanc.json`):
backend pytest (60) → frontend tsc → lint → vitest (298) → docker-e2e
(22 Browser-Tests + DIMSE-Smokes). Verifiziert: alle Stages grün.
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
| 5 | OE3: Editoren für Quellen/Ziele/Regeln/Modify/Settings + Audit-Events | ✅ |
| 6 | Härtung: TLS, Alerting (Retention-Purge ist implementiert) | ☐ |
| 7 | HL7-Adapter (ORM/ADT → lokale MWL-Quelle) | ☐ |

## Offene Punkte / Risiken

- **Charset** je Quelle testen (deutsche Namen, `ISO_IR 100` vs `ISO_IR 192`).
- **Dedupe-Strategie** muss fachlich bestätigt werden (gleicher Patient in
  zwei RIS? Accession-Kollisionen?).
- `seen_items` als Routing-Basis funktioniert nur, wenn die Worklist vorher
  abgefragt wurde — Fallback-Regel zwingend konfigurierbar.
- Orthanc kann parallel weiterhin Bilder direkt annehmen (Port 4242); der
  Broker-Port 11113 ist der empfohlene Eingang für Modalitäten.
