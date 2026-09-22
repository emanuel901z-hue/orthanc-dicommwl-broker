# orthanc-dicommwl-broker

Workspace für einen **DICOM Modality-Worklist-Broker** mit sauberem Konfigurations-
Interface und Monitoring, aufgebaut auf:

| Komponente | Pfad | Zweck |
|---|---|---|
| `orthanc-explorer-3-usable/` | Frontend (Submodule) | OE3-Fork (React SPA) — Konfigurations- und Monitoring-UI für den Broker |
| `mwl-broker/` | Backend | Python-Service (FastAPI + pynetdicom): MWL-SCP (C-FIND-Proxy/Aggregator), C-STORE-SCP mit Quellen-Routing, Config-API, Query-/Store-Log, Prometheus-Metriken |
| `docker-compose.yml` | Stack | Orthanc + Postgres-Index + Broker + OE3 (produktionsfähige Basis) |
| `docker-compose.demo.yml` | Overlay | Zwei Mock-RIS-Quellen + zweites PACS zum Testen des Routings |
| `setup.sh` | Erstinbetriebnahme | Geführter Produktiv-Bootstrap: prüft Umgebung/`.env`/Ports, füllt fehlende oder schwache Werte, startet den Stack, richtet RBAC/AET-Whitelist/TLS/Alarmierung/Aufbewahrung ein — mit Sicherung und Rückfragen ([Details](docs/production-setup.md)) |
| `build.sh` | Betrieb | Bauen, starten, prüfen, stoppen, Registry — alle Optionen erklärt (`--help`); `bootstrap.sh` ist nur noch ein Wrapper darauf |
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
./setup.sh                # Produktiv: geführt (prüft, konfiguriert, startet)
./setup.sh --check        # nur prüfen, was noch offen ist
./build.sh                # Alternative ohne Führung: bauen + starten
./build.sh --demo         # inkl. Mock-RIS-Quellen + zweitem PACS
./build.sh --check        # nur Vorprüfung, baut nichts
./build.sh --help         # alle Optionen erklärt
```

`build.sh` prüft Docker (und installiert es auf Wunsch mit
`--install-docker`), legt `.env` aus `.env.example` an, warnt bei
Port-Kollisionen (wichtig auf Hosts mit anderen Docker-Projekten), baut die
Images, wartet auf die Erreichbarkeit und zeigt am Ende die Adressen und den
Smoke-Test-Befehl.

### Die wichtigsten Optionen

| Aufruf | Wirkung |
|---|---|
| `./build.sh` | Basis-Stack bauen und starten (postgres, orthanc, mwl-broker, oe3) |
| `./build.sh mwl-broker oe3` | Nur diese Services — nach einer Code-Änderung |
| `./build.sh --demo` | Demo-Services zusätzlich (Mock-RIS, Peer-PACS) — nie produktiv |
| `./build.sh --viewer` | OHIF-Viewer zusätzlich (Build 5–10 min) |
| `./build.sh --no-cache` / `--pull` | Ohne Cache bauen / Basis-Images aktualisieren |
| `./build.sh --check` | Nur Vorprüfung: Docker, `.env`, Ports |
| `./build.sh --health` | Nach dem Start warten, bis alles „healthy" ist |
| `./build.sh --ps` / `--logs mwl-broker` | Status ansehen / Logs folgen |
| `./build.sh --restart` / `--down` | Neustarten ohne Build / stoppen |
| `./build.sh --down --volumes` | Stoppen **und Daten löschen** (fragt nach) |
| `./build.sh --tag REG/mwl --push` | Images für eine Registry taggen und pushen |
| `./build.sh --dry-run` | Nur anzeigen, was passieren würde |

`bootstrap.sh` bleibt als Wrapper erhalten (alte Anleitungen funktionieren
weiter) und installiert Docker wie bisher automatisch, wenn es fehlt.

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
| Broker B (HA) | 18091 / 11123 / 2763 | optional (`--profile ha`), nur `127.0.0.1` — zweite Instanz auf gemeinsamer DB und gemeinsamem Spool-Volume |

### OHIF-Viewer (optional)

Der gehärtete OHIF v3.12.5-Build (`ohif-viewer/`) inklusive der eigenen
Extension-Panels (`extension-radiology-advanced/`) ist als Compose-Profil
angebunden. Er läuft **same-origin** unter `/ohif/` hinter dem OE3-nginx —
damit funktioniert der „In OHIF öffnen"-Button der Studienansicht direkt,
und DICOMweb kommt aus dem mitgelieferten Orthanc (`/orthanc-proxy/dicom-web`).

```bash
# baut OHIF aus dem Quelltext (Clone + Install + Build, ~5-10 min beim ersten Mal)
docker compose --profile viewer up -d --build ohif
# oder beim Start: ./build.sh --viewer

# Aufruf:  http://<host>:18082/ohif/viewer?StudyInstanceUIDs=<UID>
#          bzw. aus OE3 heraus über den Button in der Studienansicht
```

Die Viewer-Config liegt in `deploy/ohif-config.js` (ins Image gemountet,
änderbar ohne Rebuild). Ohne das Profil startet der Stack unverändert —
`/ohif/` liefert dann nur einen Fehler.

### Hochverfügbarkeit (optional)

Ein einzelner Broker ist ein Single Point of Failure für alle Modalitäten.
`docker compose --profile ha up -d` startet eine **zweite Instanz**, die sich
Datenbank und Spool-Volume mit der ersten teilt:

```bash
docker compose --profile ha up -d
curl -s http://127.0.0.1:18081/api/v1/status | python3 -m json.tool   # "instances"
./deploy/ha-smoke.sh          # Live-Nachweis: keine Doppelzustellung
```

Beide Instanzen dürfen gleichzeitig arbeiten — ein Bild wird trotzdem genau
**einmal** zugestellt (atomarer Spool-Claim mit Lease, Migration 0014). Was der
Broker **nicht** kann: seine Adresse verschieben. Die Modalitäten erreichen die
aktive Instanz über eine schwebende IP oder einen TCP-Load-Balancer
(Health-Check: `/healthz/ready`). Details, Grenzen und das Runbook-Kapitel:
[`docs/ha.md`](docs/ha.md).

### Smoke-Tests

```bash
# C-FIND gegen den Broker (liefert gemergte Antworten der Mock-RIS):
python3 mwl-broker/scripts/cfind_smoke.py 127.0.0.1 11113 MWLBROKER

# Oder nach dem Boot im Browser: http://<host>:18082/oe3/ → "MWL Broker"
# zeigt Echo-Matrix, Zähler und das Live-Query-Log.
```

## Repository-Beschreibung

Die Texte für den GitHub-„About"-Bereich (Beschreibung, Themen, Release-Notizen
und eine PR-Vorlage) liegen fertig in
[docs/github-repo-about.md](docs/github-repo-about.md).

## Bekannte Stolpersteine (behoben)

- **`GET /worklists` → 404 im Browser-Log**: Orthancs Worklists-Plugin-API ist in
  diesem Stack bewusst aus (MWL macht der Broker). Die OE3-Seite ist jetzt über
  `enableWorklists` gegated — kein Eintrag, keine Anfrage, keine Konsolenfehler.
  Zum Aktivieren: `"Worklists": {"Enable": true}` in `deploy/orthanc/orthanc.json`
  **und** `enableWorklists: true` in `deploy/oe3-config.js`.
- **Rohwerte in der Oberfläche** (`success`, `partial`, `open`, Ereignis- und
  Retention-Texte, Einstellungs-Beschreibungen): alle API-Werte laufen jetzt
  durch i18n (`broker.queryStatus_*`, `broker.event_*`, `broker.retentionTable_*`,
  `broker.settingDesc_*`) mit dem API-Text als Fallback.
- **Tabellenzeilen waren nicht klickbar**: ein Klick (oder Enter/Leertaste) auf
  eine Zeile öffnet jetzt die Bearbeitung — in allen Broker-Listen.

## API-Dokumentation

Für Ausschreibungen und die Abnahme mit Modalitäten-Herstellern:
[DICOM Conformance Statement](docs/dicom-conformance-statement.md) und
[IHE-Profil-Aussage](docs/ihe-profile-statement.md) — beide durch einen Test an
den Code gebunden.

Die IHE-Aussage ordnet zusätzlich **IHE MADO** ein: der Broker ist dort bewusst
**kein** Akteur (MADO ist Content-Zugriff, der Broker Workflow) — mit Begründung,
Berührungspunkten und benannter Lücke, damit eine Ausschreibung nicht an einer
fehlenden Zeile scheitert. Zwei Berührungspunkte sind umgesetzt:

- **IID (Invoke Image Display, RAD-106)** — OE3 öffnet den Viewer über
  `/oe3/IHEInvokeImageDisplay?requestType=STUDY&studyUID=…` (auch
  `accessionNumber=…` bzw. `?requestType=PATIENT&patientID=…`); derselbe Weg,
  den ein fremdes RIS/KIS nimmt, wird auch von der eigenen Oberfläche benutzt.
- **Auftragskontext** — `GET /api/v1/orders/context?study_uid=…` (oder
  `?accession=…`) beantwortet „zu welchem Auftrag gehört diese Studie?"
  (Accession, SPS-ID, Station, Herkunft, MPPS-Zustand) und bindet damit ein
  Manifest an den Auftrag. PHI-frei: der Patientenname verlässt den Broker nie.

Der Vergleich mit kommerziellen MWL-Brokern (Funktionslücken, priorisierte
Sprints) steht in [`docs/commercial-comparison.md`](docs/commercial-comparison.md).

Die Test-Abdeckung (pytest, vitest, Playwright, Chrome-headless-DOM-Audit (146 Checks) und
der Screenshot-Walk über alle Views) ist in
[`docs/test-coverage-audit.md`](docs/test-coverage-audit.md) dokumentiert.

Die Vollständigkeitsprüfung der API (Routen ↔ UI-Aufrufe ↔ Tests ↔ Doku,
inklusive Live-Belegen und offenen Befunden) steht in
[`docs/api-completeness-audit.md`](docs/api-completeness-audit.md).

Swagger UI: `http://<broker>:8081/docs` · ReDoc: `/redoc` ·
Spezifikation: `/openapi.json` — jede Operation mit Beschreibung, dokumentierten
Parametern und Fehlerantworten (der Vertrag wird per Test erzwungen).

## Stand

**Broker v1.0.0** — alle Roadmap-Themen (P0/P1/P2) sind umgesetzt, dazu die
UI-Härtung aus der DAU-Gap-Analyse, die MFA-Testumgebung und die i18n-Aufräumung.
Die OpenAPI-Dokumentation ist vollständig (78 Operationen, jede mit Beschreibung,
Parametern und Fehlerantworten). Aktuelle Zahlen:
571 Backend-Tests (96 %), 590 Frontend-Tests, 55 Browser-E2E-Tests, 146 Checks
im Deep-Audit — alles in `./ci-local.sh` verdrahtet.

## Tests

```bash
cd mwl-broker && python -m pytest tests -q        # 571 Tests (API + DIMSE e2e + MPPS/MLLP/TLS/RBAC/Retention/HL7/ATNA/UPS-RS/Auftragskontext/ADT/Hochverfügbarkeit/Nebenläufigkeit)
cd orthanc-explorer-3-usable && npm run test      # 590 Tests

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
- [x] Dev-/Demo-Stack, .env-basierte Konfiguration, build.sh (bootstrap.sh als Wrapper)
- [x] OE3: `broker.ts` API-Client + Broker-Dashboard
- [x] Tests: 60 Backend, 45 Frontend neu (inkl. Konfig-UI + Audit-Vertrag)
- [x] Verifiziert auf Zielhost: C-FIND-Fan-out, Dedupe, Store-Routing, Echo
- [x] Browser-E2E (Playwright, Desktop+Mobile): 22/22 grün, 0 Console-Errors
- [x] OE3: vollständige Konfigurations-UI — Quellen, Ziele, Routing-Regeln,
      Modify-Regeln (DICOM-Tag-Transformationen), Laufzeit-Settings (Audit-Events)
- [x] Retention-Purge für seen_items (Settings-gesteuert)
- [x] Sprint 1 (Roadmap): Circuit Breaker pro Upstream + Konfigurations-Health-Panel
      inkl. `/healthz/ready` — Details im [Umsetzungs-Log](docs/roadmap-worklist-broker.md#umsetzungs-log)
- [x] Sprint 2 (Roadmap): Simulation/Dry-Run (Routing + Modify-Regeln),
      serverseitiges Änderungsprotokoll mit Rollback sowie Config-Export/-Import
      — Details im [Umsetzungs-Log](docs/roadmap-worklist-broker.md#sprint-2--simulation--config-auditexportimportrollback-umgesetzt)
- [x] Sprint 3 (Roadmap): Worklist-Cache mit Stale-Fallback (Snapshot-Semantik
      wie Medavis/dcm4chee — der Upstream bleibt die Wahrheit) — Details im
      [Umsetzungs-Log](docs/roadmap-worklist-broker.md#sprint-3--worklist-cache-mit-stale-fallback-umgesetzt)
- [x] Sprint 4 (Roadmap): C-STORE-Spool mit Retry/Dead-Letter (Store and Forward,
      Payload auf eigenem Volume, Alembic-Migrationspfad) — Details im
      [Umsetzungs-Log](docs/roadmap-worklist-broker.md#sprint-4--c-store-spool-mit-retrydead-letter-umgesetzt)
- [x] Sprint 5 (Roadmap): Alerting/Webhooks — Ereigniskatalog, gedämpfte
      Zustellung an Slack/Teams-kompatible Webhooks, Testversand aus der UI —
      Details im [Umsetzungs-Log](docs/roadmap-worklist-broker.md#sprint-5--alertingwebhooks-umgesetzt)
- [x] Sprint 6 (Roadmap): P2 — lokale Worklist-Items + HL7-ORM-Adapter (REST und
      MLLP), Per-Station-Filter/-Priorität, ATNA-Audit-Export (Syslog/TLS an die
      eigene Gegenstelle) — Details im
      [Umsetzungs-Log](docs/roadmap-worklist-broker.md#sprint-6--p2-lokale-worklisthl7-stationsregeln-atna-umgesetzt)
- [x] Sprint 7 (Roadmap): DICOM-TLS/mTLS mit Zertifikatsverwaltung — zweiter
      TLS-Listener neben dem Klartext-Port, TLS je Quelle/Ziel, Erzeugung
      selbstsignierter Zertifikate, Ablaufüberwachung und Endpunkt-Prüfung —
      Details im [Umsetzungs-Log](docs/roadmap-worklist-broker.md#sprint-7--dicom-tlsmtls--zertifikatsverwaltung-umgesetzt)
- [x] Sprint 8 (Roadmap): Betreiberentscheidungen umsetzbar — RBAC
      (brokerRead/brokerWrite hinter dem Proxy), Retention/Löschkonzepte
      (konfigurierbar + sichtbar), flexibles Alerting (mehrere Webhooks) —
      Details im [Umsetzungs-Log](docs/roadmap-worklist-broker.md#sprint-8--betreiberentscheidungen-umsetzbar-gemacht-umgesetzt)
- [ ] Alle Roadmap-Themen sind umgesetzt; die Betreiberentscheidungen sind in
      der [Roadmap](docs/roadmap-worklist-broker.md#offene-entscheidungen-an-den-betreiber)
      konfigurierbar dokumentiert.
- [x] Sprint 9 (UI-Härtung P1): Rückmeldung für jede Einstellung (Toast +
      Inline-Fehler), typisierte/begrenzte Eingaben aus der API, Warnung bei
      gefährlichen Stationsregeln, Dialoge auf kleinen Bildschirmen bedienbar —
      Details in der [DAU-Gap-Analyse](docs/ui-dau-gap-analysis.md#sprint-9--ui-härtung-p1-umgesetzt)
- [x] Sprint 10 (Eingabeführung): Datum/Zeit-Picker, Auswahlen und Muster in
      der lokalen Worklist, Vorprüfung mit denselben Regeln wie der Server,
      ein Schreibvorgang pro Änderung statt bei jedem Tastendruck, Konsequenz
      beim Löschen des Standard-Ziels — Details in der
      [DAU-Gap-Analyse](docs/ui-dau-gap-analysis.md#sprint-10--eingabeführung-umgesetzt)
- [x] Sprint 11 (Bedienfluss): Dirty-Guard in allen Formularen,
      Duplikat-Hinweise (AET, Quelle+Ziel), Tag-Vorprüfung, einheitliche
      Beschriftungen, Barrierefreiheit — **alle 19 Befunde der
      [DAU-Gap-Analyse](docs/ui-dau-gap-analysis.md#8-abschluss) bearbeitet**
- [x] MFA-Testumgebung: die Journey eines unbedarften Anwenders
      (`./mfa-test.sh`) prüft Fehleingaben, verständliche Meldungen, Korrigieren,
      Zurück/F5 und gefährliche Konfigurationen — Bericht unter
      `orthanc-explorer-3-usable/e2e/stack/screenshots/mfa-journey-*.md`,
      Befunde in [docs/mfa-usability-test.md](docs/mfa-usability-test.md);
      Entwürfe (auch für Regel-/Transform-Formulare, Ablauf nach 1 h) und eine
      „Was ist das?"-Hilfe auf jeder Seite
- [x] i18n aufgeräumt: nur react-i18next (kein eigenes `t()`), Broker-Rahmen in
      allen 9 OE3-Sprachen, Debug über `?lng=`/`?i18nDebug=1`, Abdeckungsprüfer
      `npm run i18n:check` in CI
- [ ] HL7-ORM/ADT-Adapter (Worklist-Einträge ohne Upstream-C-FIND)
