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
./setup.sh                  # Erstinbetriebnahme: prüft/füllt .env, Ports, RBAC, TLS, Alarmierung
./setup.sh --check          # nur prüfen (ändert nichts) — auch für Bestandsanlagen
./setup.sh --self-test      # Prüffunktionen testen (ohne Docker, CI-fähig)
./build.sh                  # Docker-Check, .env anlegen, Port-Check, build + up + Health
./build.sh --demo           # inkl. docker-compose.demo.yml
./build.sh --check          # nur Vorflight (Docker, .env, Ports)
./build.sh --health         # warten, bis alle Container "healthy" melden
./build.sh --logs mwl-broker
./build.sh --down [--volumes]
./build.sh mwl-broker oe3   # nur einzelne Services neu bauen
./build.sh --help           # alle Optionen (Tag/Push, no-cache, pull, dry-run …)
./bootstrap.sh              # Wrapper um build.sh (installiert Docker bei Bedarf)
docker compose up -d --build
docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d

# Broker-Tests (ohne Docker; DIMSE-Tests nutzen ephemere Ports + sqlite)
cd mwl-broker && python -m pytest tests -q
# …mit Coverage (aktuell 96 %)
cd mwl-broker && .venv/bin/pytest tests -q --cov=mwl_broker --cov-report=term-missing

# RBAC + Retention (laufender Stack)
curl -s http://127.0.0.1:18081/api/v1/rbac/status | python3 -m json.tool
curl -s http://127.0.0.1:18081/api/v1/retention | python3 -m json.tool
curl -X POST http://127.0.0.1:18081/api/v1/retention/purge   # auditiert
# Schreibzugriff erzwingen (Proxy übergibt die Rollen):
curl -X PUT http://127.0.0.1:18081/api/v1/settings/rbac_mode \
  -H 'Content-Type: application/json' -H 'X-OE3-Roles: brokerWrite' \
  -d '{"value":"enforce"}'

# DICOM-TLS (laufender Stack)
curl -s http://127.0.0.1:18081/api/v1/tls/overview | python3 -m json.tool
curl -s -X POST http://127.0.0.1:18081/api/v1/tls/self-signed -H 'Content-Type: application/json' \
  -d '{"common_name":"mwl-broker.hospital.local","days":365,"san":["10.0.1.47"]}' | python3 -m json.tool
curl -s -X POST http://127.0.0.1:18081/api/v1/tls/test -H 'Content-Type: application/json' \
  -d '{"host":"127.0.0.1","port":2762,"echo_aet":"MWLBROKER"}' | python3 -m json.tool
# C-FIND über den TLS-Listener (Test-Stack-Port 19083):
python3 mwl-broker/scripts/cfind_smoke.py 127.0.0.1 19083 MWLBROKER --tls --ca /tmp/ca.pem

# Lokale Worklist + HL7 (laufender Stack)
curl -s http://127.0.0.1:18081/api/v1/local-items | python3 -m json.tool
curl -s -X POST http://127.0.0.1:18081/api/v1/hl7/orm?dry_run=true \
  -H 'Content-Type: text/plain' --data-binary @/tmp/orm.hl7 | python3 -m json.tool
curl -s http://127.0.0.1:18081/api/v1/hl7/messages?limit=10 | python3 -m json.tool

# Stationsregeln + Vorschau
curl -s http://127.0.0.1:18081/api/v1/station-rules | python3 -m json.tool
curl -s -X POST http://127.0.0.1:18081/api/v1/simulate/station \
  -H 'Content-Type: application/json' -d '{"station_aet":"CT_01"}' | python3 -m json.tool

# ATNA-Audit-Trail
curl -s http://127.0.0.1:18081/api/v1/atna/stats | python3 -m json.tool
curl -s http://127.0.0.1:18081/api/v1/atna/sample | python3 -c "import json,sys; print(json.load(sys.stdin)['xml'])"
curl -X POST http://127.0.0.1:18081/api/v1/atna/test

# Alerting (laufender Stack)
curl -s http://127.0.0.1:18081/api/v1/notify/events | python3 -m json.tool
curl -X POST http://127.0.0.1:18081/api/v1/notify/test
# Webhook konfigurieren (URL + Ereignisse):
curl -X PUT http://127.0.0.1:18081/api/v1/settings/notify_webhook_url \
  -H 'Content-Type: application/json' -d '{"value":"https://hooks.example/x"}'
curl -X PUT http://127.0.0.1:18081/api/v1/settings/notify_events \
  -H 'Content-Type: application/json' -d '{"value":"source_down,spool_dead_letter"}'

# C-STORE-Spool (laufender Stack)
curl -s http://127.0.0.1:18081/api/v1/spool/stats | python3 -m json.tool
curl -s 'http://127.0.0.1:18081/api/v1/spool?status=dead' | python3 -m json.tool
curl -X POST http://127.0.0.1:18081/api/v1/spool/retry-all
curl -X DELETE 'http://127.0.0.1:18081/api/v1/spool/1?reason=duplicate'

# Schema-Migrationen
cd mwl-broker && .venv/bin/alembic current && .venv/bin/alembic history

# Worklist-Cache (laufender Stack)
curl -s http://127.0.0.1:18081/api/v1/cache/stats | python3 -m json.tool
curl -s 'http://127.0.0.1:18081/api/v1/cache/items?limit=5' | python3 -m json.tool
curl -X DELETE http://127.0.0.1:18081/api/v1/cache

# Simulation + Änderungsprotokoll (laufender Stack)
curl -s -X POST http://127.0.0.1:18081/api/v1/simulate/route \
  -H 'Content-Type: application/json' -d '{"accession":"ACC-A-001"}' | python3 -m json.tool
curl -s http://127.0.0.1:18081/api/v1/audit/config?limit=5 | python3 -m json.tool
curl -s http://127.0.0.1:18081/api/v1/config/export > /tmp/broker-config.json
curl -s -X POST 'http://127.0.0.1:18081/api/v1/config/import?dry_run=true' \
  -H 'Content-Type: application/json' -d @/tmp/broker-config.json | python3 -m json.tool

# Auftragskontext: zu welchem Auftrag gehört diese Studie? (für MADO-Manifest-Erzeuger)
curl -s 'http://127.0.0.1:18081/api/v1/orders/context?study_uid=1.2.3' | python3 -m json.tool
curl -s 'http://127.0.0.1:18081/api/v1/orders/context?accession=ACC-A-001' | python3 -m json.tool
# IID (Invoke Image Display, RAD-106) — der Weg, den auch ein fremdes RIS/KIS nimmt:
#   http://127.0.0.1:18082/oe3/IHEInvokeImageDisplay?requestType=STUDY&studyUID=<UID>
#   http://127.0.0.1:18082/oe3/IHEInvokeImageDisplay?requestType=STUDY&accessionNumber=<ACC>
#   http://127.0.0.1:18082/oe3/IHEInvokeImageDisplay?requestType=PATIENT&patientID=<ID>

# Broker-API + Swagger/OpenAPI (laufender Stack)
curl -s http://127.0.0.1:18081/openapi.json | python3 -m json.tool | head
#   Swagger UI: http://127.0.0.1:18081/docs
#   Konfigurations-Checks / Readiness / Breaker-Reset:
curl -s http://127.0.0.1:18081/api/v1/health/config | python3 -m json.tool
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:18081/healthz/ready
curl -X POST http://127.0.0.1:18081/api/v1/sources/1/reset-breaker

# Broker lokal (Postgres via Docker, sonst BROKER_DATABASE_URL setzen)
cd mwl-broker && uvicorn mwl_broker.main:app --port 8081

# Frontend
cd orthanc-explorer-3-usable
npm install
npm run dev                 # Vite-Proxy: /orthanc-proxy, /broker-api
npm run test && npm run lint
npx tsc --noEmit -p tsconfig.app.json
npx vitest run --coverage    # Broker-UI-Coverage (aktuell 98,9 %)

# Hochverfügbarkeit (zweite Instanz auf gemeinsamer DB + Spool-Volume)
docker compose --profile ha up -d            # broker-a + broker-b
./deploy/ha-smoke.sh                         # Live-Nachweis: keine Doppelzustellung
./deploy/ha-smoke.sh --keep                  # danach stehen lassen (--down räumt ab)
curl -s http://127.0.0.1:18081/api/v1/status | python3 -c "import json,sys; print(json.load(sys.stdin)['instances'])"

# Deep-UI-Audit gegen den laufenden Stack (DOM-Checks + CRUD vs. REST-API,
# Desktop 1400x900 + Mobile 375x812, Screenshots in e2e/stack/shots/)
node e2e/stack/verify-ui.cjs

# Lasttest (misst das laufende System über die Leitung — DIMSE + REST).
# Gegen den ISOLIERTEN Test-Stack fahren, nie gegen eine Anlage im Betrieb:
# der Lasttest füllt Spools. Erst die Gegenstelle messen, dann den Broker
# (der Mock-RIS war schon einmal der Flaschenhals) — siehe docs/loadtest.md.
docker compose --project-name mwl-test --env-file .env.test \
  -f docker-compose.yml -f docker-compose.demo.yml up -d
python3 mwl-broker/scripts/loadtest.py cfind --port 11123 --api http://127.0.0.1:19081 \
  --clients 40 --queries 5 --concurrency 10 --json /tmp/cfind.json
python3 mwl-broker/scripts/loadtest.py cstore --port 11123 --api http://127.0.0.1:19081 \
  --instances 200 --concurrency 8 --payload-kb 64
docker compose --project-name mwl-test --env-file .env.test \
  -f docker-compose.yml -f docker-compose.demo.yml down -v

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

- **Löschpfade räumen Abhängigkeiten auf.** `DELETE /sources|targets/{id}`
  entfernt zuvor Regeln, Transforms, `seen_items` und Breaker-Zustand in
  derselben Transaktion (`before_delete`-Hook in `api._crud`) — sonst schlägt
  der Delete auf Postgres mit einem FK-Verstoß fehl.
- **SQLite-Tests erzwingen Fremdschlüssel** (`PRAGMA foreign_keys=ON` in
  `db.get_engine`), damit sich Tests wie Postgres verhalten.
- **Simulation und Echtbetrieb teilen den Code.** Zielauflösung liegt in
  `routing.py`, Modify-Regeln in `transforms.py` — beides wird vom C-STORE-Pfad
  *und* von `simulate.py` aufgerufen. Nie eine zweite Auflösung implementieren,
  sonst ist der Dry-Run wertlos.
- **Konfigurationsmutationen werden protokolliert** (`audit.record` in der
  API-Schicht, Before/After-Snapshot). Neue Mutationen ohne Audit-Eintrag sind
  unvollständig.
- **Cache-Semantik nicht aufweichen.** Eine erfolgreiche Quell-Antwort
  *ersetzt* den Snapshot (`cache.store_snapshot`), sie wird nie gemergt — sonst
  bleiben abgeschlossene Aufträge liegen. Stale nur bei Fehler/offenem Breaker,
  erledigte Schritte (`(0040,0020)`) nie aus dem Cache. Der Payload enthält PHI:
  nie loggen, nie über die API ausgeben (nur `cache.items()`-Metadaten).
- **Nachträglich ergänzte Modellspalten brauchen eine Alembic-Revision** in
  `migrations/versions/` — bestehende Postgres-Instanzen bekommen sie sonst
  nicht (`create_all` ändert vorhandene Tabellen nie) und die API antwortet mit
  500. Revisionen nach der Baseline müssen **defensiv** sein (Existenzprüfung),
  weil eine frische DB das Schema schon hat. `tests/test_db.py` erzwingt das.
- **Jede Schreibaktion meldet sich zurück.** `useAuditedMutation` zeigt Erfolg
  als Toast und Fehler als Toast + (wo vorhanden) Inline-`role="alert"`; die
  Settings-API liefert `min`/`max`/`choices`, damit die UI ihre Eingaben
  begrenzen kann statt auf 422er zu warten.
- **RBAC ist eine Middleware, kein Endpunkt-Code.** `rbac_mode=enforce` blockt
  jeden Nicht-GET auf `/api/v1/*` ohne die Write-Rolle; der Status-Endpunkt
  (`/rbac/status`) liefert der UI `can_write` für den Banner.
- **Retention: nichts implizit löschen.** `0` Tage = für immer (Änderungs-
  protokoll ist Default 0); Purge nur über die API (auditiert) oder den
  periodischen Tick.
- **TLS bleibt opt-in und getrennt pro Richtung.** Eingehend = zweiter Listener
  (Klartext läuft weiter), ausgehend = je Knoten `tls`/`tls_verify`. `tls_verify`
  nur bewusst abschalten (Health-Warnung). `tls_args` braucht **immer** den
  Server-Namen, sonst verweigert Python die Hostnamen-Prüfung.
- **Private Schlüssel nie über die API ausgeben** (nur Zertifikate); erzeugte
  Schlüssel mit 0600 schreiben.
- **Nur Auftragstypen werden angewandt — der Typ wird geprüft, nicht geraten.**
  `hl7.parse()` liest ORC/OBR/PID und würde auch eine `ORU^R01` (Befund)
  „verstehen": `order_control` fällt auf `NW` zurück, die Accession kommt aus
  OBR-3, und ohne Warnung entstünde ein Arbeitslisten-Eintrag für einen Befund.
  Deshalb gilt `hl7.is_order_message` (`ORM^O01`, `OMG^O19`) an **einer** Stelle
  (`local_worklist.upsert_from_hl7`, damit REST und MLLP gleich reagieren), und
  `hl7.describe_message_type` liefert die Begründung im Klartext. Neue
  Nachrichtentypen gehören in `ORDER_MESSAGE_TYPES` — nicht in eine zweite
  Prüfung irgendwo sonst.
- **HL7-Feldindizes sind HL7-Feldnummern.** MSH ist die Ausnahme: MSH-1 *ist*
  das Trennzeichen, deshalb `_field(seg, n, msh=True)` (Index n−1). Alle anderen
  Segmente sind 1-basiert.
- **Lokale Einträge nie mit Patientendaten ins Änderungsprotokoll.** Der
  Audit-Snapshot enthält nur Termindaten; sonst landet PHI im
  Konfigurations-Export. Die Tabelle selbst ist der PHI-Speicher.
- **Feldweiser Merge nur über Regeln.** Der Standard bleibt „ganzes Item von der
  Quelle mit der höchsten Priorität"; `merge_rules.apply_field_rules` überschreibt
  einzelne Attribute (vor dem Stationsfilter, damit Sichtbarkeitsregeln das
  Endergebnis sehen). Schreiben auf Datasets **immer per `setattr`** — `ds[tag] = …`
  wirft in pydicom „Dataset items must be 'DataElement' instances".
- **HL7-Zusatzfelder kommen aus `hl7_field_map`, nie aus Code.** Komponenten
  werden wie in HL7 gezählt (1-basiert, 0 = ganzes Feld); gefüllte Werte landen in
  `local_worklist_item.extra_attributes` und damit in der C-FIND-Antwort.
- **MPPS: Zustellung nie im DIMSE-Thread.** N-CREATE/N-SET nehmen an, speichern
  und melden asynchron (Thread) an das RIS zurück; Fehler werden gezählt und sind
  über `/api/v1/mpps/forward-pending` erneut auslösbar. Die MPPS-SOP-Klasse wird
  nur angeboten, wenn `mpps_enabled` — sonst nimmt der Broker Schritte an, die er
  nicht zurückmelden kann, und das RIS wartet ewig. Fertige Schritte
  (`mpps_hide_completed`) verschwinden aus der gelieferten Arbeitsliste.
- **Audit-/Alerting-Zustellung blockiert nie den DICOM-Pfad** (Queue bzw.
  Hintergrund-Thread); ATNA ist opt-in, Fehler werden nur gezählt.
- **Alerting darf nie blockieren.** Versand läuft auf einem Hintergrund-Thread,
  Fehler werden nur geloggt/gezählt. Gemeldet wird der Übergang, nicht jeder
  Check (sonst Nachrichtenflut); die Webhook-URL nie vollständig loggen.
- **Spool-Semantik**: Payload auf Platte (atomar geschrieben), DB nur Metadaten;
  Datei nach Zustellung löschen, Zeile als Duplikatsschutz behalten. Bei vollem
  Budget **abweisen**, nie still verwerfen. `spool.is_duplicate` im Live-Pfad
  verhindert doppelte Zustellungen.
- **Import ist Upsert-only** (`config_io`): nie implizit löschen; Referenzen im
  Export laufen über Namen, nicht IDs.
- **Neue Endpunkte brauchen den vollen OpenAPI-Vertrag** (Summary, Tag,
  Response-Description ≠ Default, alle Path-/Query-Params, Schema-Felder) —
  `test_openapi_documents_all_endpoints` erzwingt das.

- **ADT: Merge entzieht die ID, Link nicht.** `A40` (Zusammenführen) entzieht die
  alte ID und zieht Daten um; `A24` (Verknüpfen) sagt nur „dieselbe Person", beide
  IDs bleiben gültig. Deshalb schreibt **nur** ein Merge die C-FIND-Antwort um
  (`merges.answer_mapping`) — `merges.resolve` folgt beiden, `answer_mapping` nur
  Merges. Ein `A40` **nach** einem `A24` für dasselbe Paar stuft zur
  Zusammenführung hoch (sonst bliebe die alte ID für immer stehen), und ein `A47`
  hebt **nie** eine Zusammenführung auf. Alle vier Ereignisse (`A08`/`A24`/`A40`/
  `A47`) leben in `adt.py` — REST und MLLP rufen dieselbe Funktion
  (`mllp.handle_message` routet über `hl7.peek_type`), sonst verhalten sich die
  Transporte unterschiedlich.
- **`A08` ändert nur die eigenen Einträge** (`local_worklist_item`) und nur die
  Felder, die die Nachricht wirklich trägt — ein Namens-Update darf kein
  Geburtsdatum leeren. Eine *zusammengeführte* ID wird vorher aufgelöst, eine
  *verknüpfte* nicht (beide sind gültig und können eigene Einträge haben).
  Zwischengespeicherte Snapshots werden bewusst **nicht** umgeschrieben: der
  Cache ist eine Upstream-Kopie mit kurzem Stale-Fenster, und die Nachricht kam
  von genau diesem Upstream.
- **PHI**: `PatientName` niemals in Logs/Metriken/DB-Logs. Erlaubt für
  Matching: AccessionNumber, SPS-ID, StudyInstanceUID. PatientID nur in
  `seen_items` mit Retention.
- **Der Spool wird beansprucht, nie einfach gelesen.** `spool.due_items()` sagt
  nur, was fällig *wäre* — der Worker ruft `claim_items` (atomar,
  `FOR UPDATE SKIP LOCKED` + Lease aus `spool_lease_s`). Ohne Claim würden zwei
  Instanzen dieselbe Zeile ziehen und dasselbe Bild zweimal senden. Nach **jedem**
  Ausgang (Erfolg/Fehler/Dead Letter) den Claim freigeben, sonst bleibt der
  Eintrag bis zum Lease-Ablauf liegen. Die Zustellsemantik ist bewusst
  **at-least-once**: ein Absturz zwischen Senden und Zurückschreiben darf ein
  Duplikat erzeugen, nie ein verlorenes Bild. Siehe `docs/ha.md`.
- **`forward()` prüft den Besitz gegen den *Aufrufer*, nicht gegen den Prozess.**
  Wer mit `instance_id="broker-a"` beansprucht hat, muss mit derselben ID
  weiterreichen (`run_once` tut das) — sonst hält die Instanz ihren eigenen
  Eintrag für fremd und stellt nichts zu.
- **Die Instanzidentität ist Konfiguration, nicht Zufall.** `BROKER_INSTANCE_ID`
  je Instanz setzen; ohne sie wird `hostname:pid` benutzt, und nach einem
  Neustart ist das ein *anderer* Name (alte Zeile bleibt als „weg" stehen).
- **Die Broker-Umgebung steht einmal** (`x-broker-environment` in
  `docker-compose.yml`) und wird von beiden Instanzen geerbt. Änderungen dort
  gelten für beide — das ist gewollt; neue Einstellungen also dort pflegen, nicht
  in der zweiten Instanz.
- **Zeilen, die zwei DIMSE-Threads gleichzeitig anlegen können, per Upsert
  schreiben.** `source_breaker` (Primärschlüssel = Quelle) und
  `worklist_cache` (Unique über Quelle + Dedupe-Schlüssel) wurden per
  Read-then-Insert geschrieben: bei zehn gleichzeitigen Abfragen kollidierte das
  mit einer `IntegrityError`, und im C-FIND-Handler wurde daraus **`0xC311`** —
  die Modalität bekam einen Fehler für eine Abfrage, die der Broker hätte
  beantworten können. Dafür gibt es `db.upsert` (`INSERT … ON CONFLICT DO
  UPDATE`, Postgres und SQLite gleich). **Zähler von der Datenbank erhöhen
  lassen** (`failures = failures + 1`), nie im Python-Code lesen-und-zurückschreiben
  — sonst geht unter einem Ausfall-Burst ein Inkrement verloren. Gefunden vom
  Lasttest (`docs/loadtest.md`), Regressionstests in `tests/test_concurrency.py`.
- **Der Mock-RIS ist ein Entwicklungswerkzeug, kein Last-Gegenüber.**
  pynetdicom's Server-Default ist **eine** Assoziation gleichzeitig; damit wies
  der Mock den parallelen Fan-out des Brokers ab und der Lasttest maß den Mock
  statt des Brokers. `--max-associations` setzen und **erst die Gegenstelle
  messen, dann den Broker**.
- **DB-Pool bewusst dimensionieren.** Der Stack hat mehrere Hintergrund-Worker
  (Echo-Loop, Spool, Retention, ATNA, MPPS-Zustellung) neben DIMSE-Handlern und
  API. Der SQLAlchemy-Standard (5 + 10 Overflow) lief unter Last voll und
  antwortete dann 500 auf einfache Lesezugriffe — deshalb
  `BROKER_DB_POOL_SIZE` (Default 10), `BROKER_DB_MAX_OVERFLOW` (20),
  `BROKER_DB_POOL_TIMEOUT` (15 s) und `pool_recycle` (30 min).
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
