# Roadmap — produktive Funktionalitäten für den MWL-Broker

Dieses Dokument bewertet, welche Funktionen dem Worklist-Broker im
Krankenhausbetrieb echten Nutzen bringen, wie sie im Backend (inkl. API und
OpenAPI-Doku) umgesetzt werden, wie sie im OE3-Frontend **DAU-sicher**
(also gegen Fehlbedienung abgesichert) angebunden werden und wie sie getestet
und verifiziert werden.

**Stand heute** (Basis der Vorschläge): MWL-C-FIND-Proxy mit Fan-out, Merge und
Dedupe · C-STORE-Routing über `seen_items` + Regeln mit Default-Fallback ·
Modify-Regeln (Tag-Transformation) · Laufzeit-Settings (ENV-Default + Override)
· C-ECHO-Monitoring, Prometheus-Metriken, PHI-freie Logs, Retention-Purge ·
vollständige Konfigurations-UI in OE3 · 88 Backend-/325 Frontend-Tests,
22 Browser-E2E-Tests, OpenAPI vollständig dokumentiert.

---

## Bewertungsmaßstab

| Kriterium | Frage |
|---|---|
| **Klinische Verfügbarkeit** | Was passiert, wenn RIS oder PACS ausfallen — kann die Modalität weiterarbeiten? |
| **Datenschutz/Compliance** | PHI-Handling, Auditierbarkeit, Löschkonzepte, Betreiberpflichten |
| **Betriebsaufwand** | Wie viel Eingriff braucht der Betrieb, wie gut ist der Zustand sichtbar? |
| **DAU-Risiko** | Kann eine Fehlkonfiguration Patienten oder Bilder kosten? Wie leicht ist sie zu erkennen/zu verhindern? |
| **Umsetzungsaufwand/-risiko** | Änderungen am DIMSE-Kernpfad sind teurer als additive Endpunkte |

**Leitlinie für alle Features:** ein sicherer Default, jede riskante Aktion
mit Vorschau/Test, jede Wirkung sichtbar im Monitoring, jede Änderung
auditierbar.

## Priorisierung im Überblick

| Prio | Funktion | Nutzen | Aufwand | Status |
|---|---|---|---|---|
| **P0** | Worklist-Cache mit Stale-Fallback | RIS-Ausfall legt den Modalitätenbetrieb nicht lahm | mittel | offen (Sprint 3) |
| **P0** | C-STORE-Spool mit Retry/Dead-Letter | kein Bildverlust bei PACS-Ausfall | hoch | offen (Sprint 4) |
| **P0** | Circuit Breaker pro Upstream | tote Quelle kostet keine Timeouts mehr | klein | **✅ Sprint 1** |
| **P1** | Config-Audit + Export/Import/Rollback | Nachvollziehbarkeit, Staging→Prod, Notfall-Rollback | mittel | offen (Sprint 2) |
| **P1** | Simulation (Dry-Run) für Routing/Transform | Regeln gefahrlos prüfen, bevor sie greifen | klein | offen (Sprint 2) |
| **P1** | Konsistenz-Checks / Health-Panel | Fehlkonfigurationen früh und sichtbar | klein | **✅ Sprint 1** |
| **P1** | Alerting/Webhooks + Readiness-Endpoint | Betrieb erfährt Störungen, bevor Anwender anrufen | klein | Readiness ✅ Sprint 1, Webhooks offen (Sprint 5) |
| **P2** | Lokale Worklist-Items / HL7-ORM-Adapter | Notfälle und ungeplante Untersuchungen | hoch | offen |
| **P2** | Per-Station-Filter und -Priorität | jede Konsole sieht nur ihre Arbeitsliste | mittel | offen |
| **P2** | DICOM-TLS (mTLS) + Zertifikatsverwaltung | Segmentierung/Netzwerkanforderungen | mittel | offen |
| **P2** | ATNA-Audit-Export (syslog/TLS) | IHE-Compliance, zentrale Auditablage | mittel | offen |

---

## P0 — Verfügbarkeit (klinisch kritisch)

### P0-1 Worklist-Cache mit Stale-Fallback

**Wert in der Produktion.** Fällt ein RIS aus oder antwortet es langsam, sieht
die Modalität eine leere oder verzögerte Arbeitsliste — die Untersuchung kann
nicht gestartet werden. Ein Cache, der zuletzt erfolgreich abgefragte
Worklist-Items kurzzeitig weiterliefert, überbrückt RIS-Neustarts, Backups und
Netzstörungen.

**Backend.**

- Neue Tabelle `worklist_cache`: `dedupe_key` (PatientID+Accession+SPS-ID,
  wie in `upstream.dedupe_key`), `source_id`, `payload` (JSON des Datasets),
  `fetched_at`, `expires_at`, `last_served_at`.
- Im C-FIND-Pfad (`dimse.handle_find`): je Quelle zuerst Cache prüfen; nur bei
  Miss oder abgelaufener TTL real abfragen. Bei Fehler der Quelle und
  `cache_stale_on_error` die letzte Antwort bis `cache_max_stale_s` liefern.
- Pro Quelle konfigurierbar: `cache_ttl_s`, `cache_stale_on_error`,
  `cache_max_stale_s` (Felder auf `MwlSource`).
- Antwort-Marker: konfigurierbarer privater Tag (z. B. `(0021,00A0)`
  `MWLBROKER_SOURCE_STATE` = `fresh|stale|live`) — optional, weil manche PACS
  private Tags verwerfen; Default aus. In jedem Fall Metrik + Log.
- Invalidation bei Cancel/Update: `DELETE /api/v1/cache/items/{dedupe_key}`
  und `DELETE /api/v1/cache` (alle).
- API: `GET /api/v1/cache/stats`, `GET /api/v1/cache/items?source=&limit=`,
  die beiden DELETE-Routen; alles mit Summary, Response-Description und
  Schema-Feldbeschreibungen (bestehender OpenAPI-Vertrag).
- Metriken: `mwl_cache_hits_total{source,state}`, `mwl_cache_entries`,
  `mwl_cache_stale_served_total{source}`.
- Settings: `cache_enabled` (Default an), `cache_default_ttl_s` (Default 120).

**Frontend (OE3).**

- Monitoring-Seite: Karte „Worklist-Cache" (Einträge, Hit-Rate, stale-Anteil).
- Quellen-Dialog: Gruppe „Cache" mit TTL, Stale-Fallback-Schalter, maximalem
  Stale-Fenster — jeweils mit Hilfetext, was das fachlich bedeutet.
- Query-Log: Badge `stale`, wenn eine Antwort aus dem Cache kam; Warnbanner
  auf `/broker`, solange eine Quelle stale bedient.
- DAU-Sicherheit: Cache ist per Default an (Verfügbarkeit vor Aktualität),
  aber die Wirkung ist **sichtbar** (Badge/Banner); „Cache leeren" nur mit
  Bestätigungsdialog; kein stilles Verhalten.

**Tests & Verifikation.**

- pytest: TTL-Ablauf, Hit/Miss, Stale-Fenster, Invalidation, Parallelzugriff.
- DIMSE-Integration (in-process): Quelle antwortet → Quelle abgeschaltet →
  C-FIND liefert weiterhin die gecachte Liste, `status=partial`, `stale`-Metrik.
- vitest: Cache-Karte, Formularfelder, Badge.
- Playwright (Desktop+Mobile): Badge nach simuliertem Quellenausfall sichtbar,
  „Cache leeren" mit Bestätigung; `verify-ui.cjs` um den Fall erweitern.
- Lasttest: 100 parallele C-FINDs gegen eine Quelle mit Cache.

**Risiken.** Der Cache enthält **PHI** (Patientenname/Geburtsdatum der
Worklist). Deshalb: TTL begrenzt, keine Logs des Inhalts, Zugriff nur über die
DB im internen Netz, Löschfunktion, Aufnahme ins Löschkonzept (siehe
Querschnittsthemen). Das ist die zentrale offene Entscheidung des Betreibers.

### P0-2 C-STORE-Spool mit Retry und Dead-Letter

**Wert in der Produktion.** Ist das Ziel-PACS nicht erreichbar, ist die
Instanz heute verloren (die Modalität bekommt einen Fehler, wiederholt aber in
der Regel nicht). Ein persistenter Spool mit Wiederholversuchen ist das
klassische „kein Bildverlust"-Versprechen kommerzieller Router.

**Backend.**

- Tabelle `store_spool`: `sop_instance_uid` (unique → Dedupe, kein
  Doppelversand), `study_uid`, `accession`, `source_id`, `target_id`,
  `payload` (BYTEA), `status` (`queued|sent|failed|dead`), `attempts`,
  `next_attempt_at`, `last_error`, `created_at`, `sent_at`.
- Ein Worker-Thread (analog zum Echo-Loop) sendet fällige Einträge mit
  exponentiellem Backoff; nach `spool_max_attempts` → `dead` + Alert.
- `strict_store_status` bleibt erhalten, bekommt aber die Policy
  `accept_when_queued`: ist der Spool aktiv und die Instanz sicher
  persistiert, meldet der Broker der Modalität **Erfolg** — das verhindert
  Wiederholungen auf Geräteseite und ist die klinisch richtige Semantik.
- Dedupe: existiert die `sop_instance_uid` bereits (`queued|sent`), wird nur
  der Status quittiert, nicht erneut gesendet.
- API: `GET /api/v1/spool?status=&limit=`, `GET /api/v1/spool/stats`,
  `POST /api/v1/spool/{id}/retry`, `DELETE /api/v1/spool/{id}`.
- Settings: `spool_enabled`, `spool_max_attempts`, `spool_backoff_s`,
  `spool_max_items`, `accept_when_queued`.
- Metriken: `mwl_spool_items{status}`, `mwl_spool_oldest_seconds`,
  `mwl_spool_forwarded_total{target}`, `mwl_spool_dead_total`.

**Frontend (OE3).**

- Monitoring: Karte „Weiterleitungs-Spool" (Warteschlange, ältester Eintrag,
  Dead-Letter-Zahl) mit Warnfarbe ab Schwellwert.
- Spool-Seite `/broker/spool`: Filter nach Status/Ziel, Detailansicht
  (Accession, Study-UID, Ziel, letzter Fehler), Aktionen „Erneut senden" und
  „Verwerfen" (Verwerfen nur mit Pflicht-Begründung → Audit).
- DAU-Sicherheit: kein automatisches Verwerfen; Verwerfen erklärt den
  Verlust („Die Instanz wird nicht ins PACS übertragen"); Backlog-Banner mit
  Direktlink; `spool_max_items` verhindert unbegrenztes Wachstum, dann
  greift wieder striktes Fehlermelden.

**Tests & Verifikation.**

- pytest: Backoff-Berechnung, Dead-Letter, Dedupe, `accept_when_queued`,
  Persistenz über Prozessneustart (SQLite/Postgres), Kapazitätsgrenze.
- Integration: Ziel abschalten → C-STORE quittiert Erfolg + `queued` →
  Ziel starten → Worker sendet → `sent` und Instanz im Ziel-PACS (HTTP-Zähler).
- vitest/Playwright: Spool-Tabelle, Retry-Klick, Verwerfen mit Begründung.
- `test-stack.sh`: das Szenario „Ziel down/up" als Smoke ergänzen.

**Risiken.** Speicherbedarf (Payloads) → `spool_max_items` + Monitoring;
Reihenfolge (FIFO je Study sinnvoll); Aufbewahrung nach `sent` (kurze
Retention, damit die Dedupe-Wirkung bleibt).

### P0-3 Circuit Breaker pro Upstream

**Wert in der Produktion.** Eine tote Quelle kostet heute bei **jeder** Query
den vollen Timeout (`timeout_s`, Default 10 s) — die Modalität wartet, der
Betrieb merkt es spät. Ein Breaker nimmt die Quelle nach N Fehlern für X
Sekunden aus dem Fan-out und testet danach halb-offen.

**Backend.**

- Zustand je Quelle (`failures`, `state` = `closed|open|half_open`,
  `open_until`), persistiert, damit ein Neustart den Zustand nicht vergisst.
- Schwellen als Settings: `breaker_fail_threshold` (Default 3),
  `breaker_open_seconds` (Default 60).
- Verhalten im Fan-out: offene Quellen werden übersprungen (Query-Log:
  `per_source[name] = "breaker_open"`), Half-Open lässt genau einen Versuch
  durch.
- API: Zustand in `/api/v1/status` ergänzen (`breaker_state`,
  `breaker_retry_in_s`), `POST /api/v1/sources/{id}/reset-breaker`.
- Metriken: `mwl_upstream_breaker_state{source}` (0/1/2).

**Frontend (OE3).**

- Monitoring/Quellen: Badge `offen`/`halb-offen` mit Restzeit im Tooltip,
  Button „Breaker zurücksetzen" (Bestätigung, Audit-Event).
- Query-Log zeigt `breaker_open` als Grund statt eines Fehlers.

**Tests & Verifikation.**

- pytest: Zustandsübergänge (closed→open→half_open→closed), Schwellen,
  Reset, Persistenz.
- Integration: Quelle abschalten → erste Queries `error`, danach
  `breaker_open` und **schnelle** Antwort (< Timeout) → Quelle starten →
  Half-Open schließt den Breaker.
- vitest/Playwright: Badge und Reset-Klick.

---

## P1 — Compliance, Betrieb und DAU-Sicherheit

### P1-1 Serverseitiges Config-Audit + Export/Import/Rollback

**Wert in der Produktion.** Wer hat wann welche Routing-Regel geändert — und
wie komme ich in 30 Sekunden auf den Stand von gestern zurück? Das ist
Betreiberpflicht (Nachvollziehbarkeit) und die wirksamste Absicherung gegen
Fehlbedienung.

**Backend.**

- Tabelle `config_audit`: `ts`, `actor`, `action`, `entity`, `entity_id`,
  `before_json`, `after_json`, `correlation_id`.
- Actor-Quelle: Header `X-OE3-User` (Setting `audit_actor_header`, Default
  aus → `"api"`). Im Standalone-Stack gibt es keine Authentifizierung; der
  Header ist die dokumentierte Andockstelle für einen vorgelagerten Proxy.
- Schreiben für **jede** Mutation (Sources, Targets, Rules, Transforms,
  Settings) zentral in der API-Schicht — nicht in den Endpunkten verstreut.
- API: `GET /api/v1/audit/config?entity=&limit=&offset=`,
  `GET /api/v1/config/export` (vollständiges JSON inkl. Version),
  `POST /api/v1/config/import?dry_run=true` (Antwort: Diff statt Schreiben),
  `POST /api/v1/config/rollback/{audit_id}`.
- Export-Format versionieren (`schema_version`), damit Importe aus älteren
  Ständen validiert und klar abgelehnt werden können.

**Frontend (OE3).**

- Seite `/broker/audit`: Änderungsprotokoll mit Filter (Entität, Zeitraum),
  Diff-Ansicht (vorher/nachher) und „Zurücksetzen auf diesen Stand".
- Import/Export-Dialog: Export als Datei-Download; Import **immer** zuerst als
  Dry-Run mit farbigem Diff und expliziter Bestätigung; Warnung, wenn die
  Datei Regeln enthält, die aktuell aktive Objekte deaktivieren würden.
- DAU-Sicherheit: Rollback ist reversibel (der Rollback selbst wird
  auditiert), Import ist zweistufig, Diff ist verpflichtend sichtbar.

**Tests & Verifikation.**

- pytest: jede Mutation erzeugt genau einen Audit-Eintrag (Parametrisierung
  über alle Ressourcen), Export→Import-Roundtrip ist idempotent,
  Dry-Run schreibt nichts, Rollback stellt den Vorzustand her, unbekannte
  `schema_version` wird abgelehnt.
- vitest: Diff-Ansicht, Dry-Run-Dialog, Bestätigungspflicht.
- Playwright: kompletter Import-Dry-Run-Flow auf dem Test-Stack.

### P1-2 Simulation (Dry-Run) für Routing und Modify-Regeln

**Wert in der Produktion.** Die häufigste Fehlerquelle sind Regeln, die
„fast" passen. Wer vor dem Speichern sieht, wohin ein konkreter Fall geht und
wie die Kopf­daten danach aussehen, konfiguriert sicher.

**Backend.**

- `POST /api/v1/simulate/route` — Eingabe `{accession, study_uid, source_id?}`
  → Antwort `{target, rule, matched_via: seen_item|study_uid|default,
  reason}`.
- `POST /api/v1/simulate/transform` — Eingabe `{accession|dataset,
  source_id?, target_id?}` → Antwort `{rules_applied, changes: [{tag, before,
  after}], errors}`.
- Beide nutzen **dieselben Funktionen** wie der Echtbetrieb
  (`dimse._resolve_target`, `transforms.applicable`/`apply_transforms`) —
  keine Zweitimplementierung, sonst ist die Simulation wertlos.
- Keine Nebenwirkungen: kein Versand, keine `seen_items`-Änderung, kein
  Eintrag im Store-Log (nur ein Audit-Eintrag „simulation").

**Frontend (OE3).**

- Auf `/broker/rules` und `/broker/transforms`: „Regel testen"-Button im
  Dialog — vor dem Speichern ausprobierbar, Ergebnis als Karte mit Ampelfarbe.
- Auf `/broker`: „Fall prüfen"-Eingabe (Accession oder Study-UID) → zeigt
  gewähltes Ziel, greifende Regel und die Tag-Änderungen.
- DAU-Sicherheit: Simulation ist der **empfohlene Pflichtschritt** in der
  Oberfläche (Hinweistext), die Warnung „Diese Regel greift für keinen
  bekannten Fall" erscheint direkt im Dialog.

**Tests & Verifikation.**

- pytest: Simulation liefert exakt dasselbe Ergebnis wie der echte Pfad
  (Property-Test über generierte Konstellationen), keine Nebenwirkungen
  (Zähler/Los unverändert).
- vitest: Dialog-Ablauf, Diff-Darstellung.
- Playwright: Regel anlegen → simulieren → erst dann speichern.

### P1-3 Konsistenz-Checks / Broker-Health-Panel

**Wert in der Produktion.** Die typischen Aussetzer sind Konfigurationsfehler:
kein Default-Ziel, Regel auf deaktiviertes Ziel, Transform mit nicht
erreichbarem PACS. Ein Panel, das das aktiv prüft, verhindert stille
Fehlkonfigurationen.

**Backend.**

- `GET /api/v1/health/config` → Liste von Findings
  `{severity: error|warning|info, code, message, entity, hint}`.
- Checks: kein Default-Ziel · mehrere Default-Ziele · Regel verweist auf
  deaktivierte Quelle/Ziel · Transform-Scope ohne aktives Ziel · keine Quelle
  mit erfolgreichem C-ECHO · Whitelist leer (alle AETs erlaubt) ·
  Spool-Backlog · Quelle stale · Broker-AET-Kollision mit einem Ziel-AET.
- `GET /healthz/ready` für Orchestrierung: DB, SCP-Listener, Spool-Worker,
  konfigurierte Quellen erreichbar (ohne die volle Echo-Matrix).

**Frontend (OE3).**

- `/broker` oben: Health-Panel mit Ampelfindings und Deep-Links direkt in das
  betroffene Formular; Badge in der Sidebar bei `error`.
- DAU-Sicherheit: Findings sind handlungsorientiert formuliert („Es ist kein
  Default-Ziel gesetzt — nicht zuordenbare Bilder werden abgewiesen"),
  nicht technisch.

**Tests & Verifikation.**

- pytest: je Check ein Positiv- und ein Negativfall; `/healthz/ready` bei
  fehlender DB/SCP.
- vitest: Panel-Rendering je Severity, Deep-Link-Ziel.
- Playwright: Fehlkonfiguration erzeugen (Default-Ziel abschalten) → Finding
  sichtbar → beheben → Finding verschwindet.

### P1-4 Alerting/Webhooks + Readiness

**Wert in der Produktion.** Der Betrieb soll es erfahren, bevor die
Radiologie anruft.

**Backend.**

- Ereignisse: Quelle/Target down (aus dem Echo-Loop), Spool-Dead-Letter,
  Backlog über Schwelle, Breaker offen, Konfigurationsfehler.
- Settings: `notify_webhook_url`, `notify_events` (CSV),
  `notify_min_interval_s` (Flankenschutz gegen Sturm).
- `POST /api/v1/notify/test` für einen Testversand aus der UI.
- Zustellung als JSON-POST (Slack/Teams-kompatibel dokumentiert), Fehler
  werden geloggt, aber nie nach außen sichtbar.

**Frontend (OE3).**

- Settings-Seite: Webhook-URL, Ereignisauswahl (Mehrfachauswahl),
  Mindestabstand, „Testnachricht senden" mit Ergebnisanzeige.

**Tests & Verifikation.**

- pytest: Ereignis→Versand, Rate-Limit, Fehlerpfad (Webhook 500 → geloggt,
  Broker funktioniert weiter), Testendpunkt.
- vitest/Playwright: Formular, Testbutton.

---

## P2 — Workflow-Erweiterungen

### P2-1 Lokale Worklist-Items / HL7-ORM-Adapter

**Wert.** Notfälle und ungeplante Untersuchungen existieren in keinem RIS.
Der Broker kann lokale Items (manuell oder per HL7 ORM/ADT) in den Fan-out
mischen und mit Priorität versehen.

**Backend.** Tabelle `local_worklist_item` (Accession, PatientID/Name,
Modality, Station, SPS-Zeit, Gültigkeit); Aufnahme in `merge_answers` mit
konfigurierbarer Priorität (`local_priority`); REST-CRUD plus
`POST /api/v1/hl7/orm` (MLLP-Listener optional, eigenes Deployment-Thema).
**Frontend.** Seite `/broker/worklist` mit Anlegen/Bearbeiten (Formular mit
DICOM-Keyword-Validierung), Gültigkeitsdauer, Kennzeichnung „lokal" im
Query-Log.
**Tests.** pytest (Merge-Reihenfolge, Ablauf/Gültigkeit, ORM-Parsing),
DIMSE-Integration (lokales Item erscheint in der C-FIND-Antwort), UI-Tests.

### P2-2 Per-Station-Filter und -Priorität

**Wert.** Eine Konsole soll nur ihre Arbeitsliste sehen; Prioritäten je
Station verhindern, dass eine Notfallquelle von einer langsamen Routinequelle
verdrängt wird.

**Backend.** Filterregeln je Station (`ScheduledStationAETitle` → Quellen
erlauben/verbieten), Prioritäts-Override je Station; Filterung erfolgt **nach**
dem Merge, damit Dedupe unverändert bleibt.
**Frontend.** Regel-Editor mit Station-Auswahl (Mehrfach), Vorschau der
Wirkung über P1-2.
**Tests.** pytest (Filtermatrix), Integration (C-FIND mit Station-AET),
Playwright.

### P2-3 DICOM-TLS (mTLS) und Zertifikatsverwaltung

**Wert.** Segmentierung/Netzwerkanforderungen im Krankenhaus; teils Pflicht
für Verkehr über Segmentgrenzen.

**Backend.** TLS-Kontext je Quelle/Ziel (CA, Client-Zertifikat, Schlüssel,
`verify_peer`); Upload der Zertifikate über die API (nur Metadaten in der DB,
Dateien im gemounteten Secret-Verzeichnis); Health-Check der Zertifikats­
gültigkeit.
**Frontend.** Dialog je Knoten mit Zertifikatsstatus (gültig bis …),
Warnung bei Ablauf < 30 Tage.
**Tests.** pytest mit Testzertifikaten (Handshake ok/abgelehnt/abgelaufen),
UI-Tests.
**Risiko.** Key-Material darf nie in der DB oder im Log landen — nur Pfade,
Dateirechte restriktiv, kein Export über die API.

### P2-4 ATNA-Audit-Export (IHE, syslog/TLS)

**Wert.** Zentrale Auditablage im KIS/SIEM, IHE-Konformität.

**Backend.** Audit-Records (Query/Store/Config) als IHE-ATNA-XML an einen
konfigurierten Audit Record Repository per syslog über TLS senden; Setting
`atna_syslog_url`, `atna_enabled`; Puffer bei Nichterreichbarkeit.
**Frontend.** Settings-Karte mit Status des letzten Versands.
**Tests.** pytest mit Mock-Syslog-Server, Formatvalidierung gegen das
ATNA-Schema.

---

## Querschnittsthemen

- **PHI-Policy.** Neu hinzu kommt PHI im Worklist-Cache (und in lokalen
  Worklist-Items). Regel: PHI nie ins Log, nie in Metriken, nie in
  Audit-`resourceId`; Cache mit TTL, Löschfunktion und Aufnahme ins
  Löschkonzept; Zugriff nur über die interne DB.
- **Retention.** `seen_items` (vorhanden), `query_log`/`store_log`,
  `store_spool` (nach `sent`), `worklist_cache`, `config_audit` (bewusst
  länger). Jede Retention über Settings steuerbar und im Health-Panel sichtbar.
- **Migrationen.** Die Mini-Migration (`db._apply_column_migrations`) trägt
  additive Spalten. Ab dem Spool (BYTEA, Indizes, Datenmigration) sollte auf
  **Alembic** gewechselt werden — einmalig, dokumentiert, mit Revisionspfad.
- **Rollen/RBAC.** Die Broker-Konfiguration schreibt produktiv wirksame
  Zustände. Über die Fork-Feature-Flags eine Trennung „ansehen" vs.
  „konfigurieren" einführen (`brokerRead`/`brokerWrite`), serverseitig über
  den `X-OE3-User`-Header bzw. Proxy-Rollen spiegelbar.
- **Doku-Pflicht.** Für jeden neuen Endpunkt gilt der bestehende
  OpenAPI-Vertrag (Summary, Tag, Response-Description, alle Path-/Query-Params
  und Schema-Felder beschrieben) — durch `test_openapi_documents_all_endpoints`
  erzwungen.
- **UI-Konventionen.** Genau ein `<h1>`, Audit-Events für Schreibzugriffe,
  Tabellen unterhalb `md` als Cards, i18n en/de, Touch-Ziele ≥ 36 px,
  Fehlermeldungen aus dem Backend im Dialog sichtbar.

## Nicht-Ziele

- Kein Ersatz für RIS/KIS oder PACS; keine eigene Bildverarbeitung
  (nur Kopfdaten-Transformation).
- Kein vollwertiger HL7-Broker (nur die für Worklists nötigen Nachrichten).
- Keine Worklist-Generierung ohne Quelle (lokale Items sind eine Ergänzung,
  keine Führung).

## Umsetzungsreihenfolge

| Phase | Inhalt | Abhängigkeit | Status |
|---|---|---|---|
| 1 | Circuit Breaker (P0-3) + Health-Panel (P1-3) | keine — schneller Nutzen, kleine Eingriffe | **✅ umgesetzt** |
| 2 | Simulation (P1-2) + Config-Audit/Export/Rollback (P1-1) | keine | offen |
| 3 | Worklist-Cache (P0-1) | Löschkonzept/PHI-Entscheidung | offen |
| 4 | C-STORE-Spool (P0-2) | Alembic-Migration, Speicherkonzept | offen |
| 5 | Alerting (P1-4), dann P2 nach fachlicher Priorisierung | Betriebsentscheidung | offen |

Jede Phase endet mit: pytest + vitest + Playwright (Desktop/Mobile) +
`verify-ui.cjs`, aktualisierter OpenAPI-Doku und aktualisiertem `project.md`.

## Umsetzungs-Log

### Sprint 1 — Circuit Breaker + Health-Panel (umgesetzt)

**Backend.**

- `SourceBreaker`-Modell (`source_breaker`-Tabelle) + `breaker.py`:
  Zustandsmaschine `closed → open → half_open → closed`, persistiert
  (Neustart vergisst eine tote Quelle nicht), Schwellen über Settings
  (`breaker_fail_threshold`, `breaker_open_seconds`).
- Integration in den C-FIND-Fan-out: offene Quellen werden übersprungen
  (`per_source = "breaker_open"`), Erfolg schließt, Fehler öffnet; die
  Query-Log-Statuslogik unterscheidet jetzt „geantwortet“ von „übersprungen“.
- `health_checks.py` mit 10 Konsistenz-Checks (`no_default_target`,
  `multiple_default_targets`, `rule_source_disabled`, `rule_target_disabled`,
  `transform_target_disabled`, `no_enabled_source`, `no_working_source`,
  `source_breaker_open`, `aet_whitelist_empty`, `broker_aet_collision`);
  Findings tragen `code`/`severity`/`entity`/`details` — die UI übersetzt.
- Neue Routen: `POST /api/v1/sources/{id}/reset-breaker`,
  `GET /api/v1/health/config`, `GET /healthz/ready` (503 wenn DB/SCP fehlen);
  `/api/v1/status` liefert `breaker_state` + `breaker_retry_in_s`.
- Metriken: `mwl_upstream_breaker_state{source}`,
  `mwl_config_findings{severity}`.
- **Nebenbefund und behoben:** `DELETE /sources|targets/{id}` lieferte auf
  Postgres 500 (FK-Verstoß), sobald Regeln, Transforms, `seen_items` oder
  Breaker-Zustand die Zeile referenzierten. Der Endpunkt räumt Abhängigkeiten
  jetzt in derselben Transaktion auf. Tests erzwingen dafür
  `PRAGMA foreign_keys=ON` auf SQLite — dieselbe Fehlerklasse fällt damit
  künftig in der Testsuite auf.

**Frontend (OE3).**

- `BreakerBadge` (Badge mit Restzeit + Reset-Button, Audit-Event
  `broker.source.breaker_reset`) in Quellentabelle, Mobile-Cards und Monitoring.
- `HealthPanel` auf `/broker`: Findings mit Schweregrad, lokalisiertem,
  handlungsorientiertem Satz, Deep-Link („Beheben“) ins betroffene Formular und
  englischem API-Text als Fallback.
- Sidebar-Badge am „MWL Broker“-Eintrag (Fehler rot, sonst Warnungen).
- Query-Log markiert `breaker_open` als „übersprungen (Breaker)“.
- Löschdialog weist auf mitentfernte Abhängigkeiten hin (DAU-Sicherheit).

**Tests & Verifikation.**

| Ebene | Umfang |
|---|---|
| pytest | 123 Tests, 97 % Coverage (+35: Zustandsmaschine, hängende Quelle → schnelle Folge-Queries, Health-Checks je Code, API, FK-Regression) |
| vitest | 348 Tests, 98,8 % Broker-UI-Coverage (+23: Badge, Panel, Mobile-Cards, Client, Audit) |
| Playwright | 25 Tests (Desktop + Mobile), inkl. Health-Panel und Breaker-Reset |
| test-stack.sh | Szenario „tote Quelle → Breaker offen → Finding → `/healthz/ready`“ |
| verify-ui.cjs | 58 Checks (Desktop 1400×900 + Mobile 375×812) |

## Offene Entscheidungen (an den Betreiber)

1. **Cache und PHI:** Ist ein kurzlebiger Worklist-Cache datenschutzrechtlich
   zulässig (TTL, Löschkonzept, Zugriffsschutz) — oder soll der Broker im
   Fehlerfall bewusst leer antworten?
2. **Spool:** erlaubte Größe/Speicherort und maximale Aufbewahrung nach
   erfolgreichem Versand.
3. **Audit-Actor:** kommt der Benutzerkontext aus einem vorgelagerten Proxy
   (Header) oder bleibt das Audit rein technisch?
4. **Alerting-Ziel:** Webhook (Teams/Slack) oder E-Mail/Syslog?
5. **TLS:** welche Strecken sind zu verschlüsseln (Modalität→Broker,
   Broker→PACS, beides)?
