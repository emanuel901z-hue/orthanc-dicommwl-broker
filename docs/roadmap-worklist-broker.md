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
| **P0** | Worklist-Cache mit Stale-Fallback | RIS-Ausfall legt den Modalitätenbetrieb nicht lahm | mittel | **✅ Sprint 3** |
| **P0** | C-STORE-Spool mit Retry/Dead-Letter | kein Bildverlust bei PACS-Ausfall | hoch | **✅ Sprint 4** |
| **P0** | Circuit Breaker pro Upstream | tote Quelle kostet keine Timeouts mehr | klein | **✅ Sprint 1** |
| **P1** | Config-Audit + Export/Import/Rollback | Nachvollziehbarkeit, Staging→Prod, Notfall-Rollback | mittel | **✅ Sprint 2** |
| **P1** | Simulation (Dry-Run) für Routing/Transform | Regeln gefahrlos prüfen, bevor sie greifen | klein | **✅ Sprint 2** |
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
nicht gestartet werden. Ein Cache, der die zuletzt erfolgreich abgefragte
Worklist kurz weiterliefert, überbrückt RIS-Neustarts, Backups und
Netzstörungen.

**Wie andere Systeme es handhaben** (recherchiert, siehe Umsetzungs-Log):

| System | Verhalten |
|---|---|
| **Medavis RIS** (Kundenbeobachtung) | Ein Eintrag wird geliefert, **bis der Auftrag im RIS abgeschlossen ist** — danach ist er aus der Warteschlange und damit weg. Präsenz ist die Wahrheit, keine TTL. |
| **dcm4chee** | MWL-Einträge werden vom ORM-Service (HL7 `ORM^O01`) angelegt/geändert/**gelöscht**; der Status läuft `SCHEDULED → ARRIVED → STARTED → COMPLETED/DISCONTINUED` über **MPPS**. `dcmHideSPSWithStatusFromMWL: COMPLETED` blendet erledigte Schritte aus; zusätzlich kann der Status gesetzt werden, sobald eine Studie vollständig empfangen wurde. |
| **DICOM-Standard** | `(0040,0020) Scheduled Procedure Step Status` ist ein Return-Key der MWL-SOP-Klasse — der standardisierte „Auftrag offen/erledigt"-Mechanismus. |
| **IHE Scheduled Workflow** | MWL (pull) und MPPS (push) sind ein Paar: **das RIS schließt Aufträge**, der Broker liefert nur aus. |
| **Flux Capacitor** (Worklist-Proxy) | Cached Snapshots je Query, **ersetzt** sie bei jedem Refresh (Snapshot-Vergleich erkennt neue Einträge), `ServeStaleForSeconds` für die Überbrückung, danach Zustand „Degraded"; `0` deaktiviert das Stale-Serving. |
| **Laurel Bridge Compass** | Worklist-Reader + Study Rules mit lokaler Pufferung/Warteschlange — gleiche Grundidee. |

**Daraus abgeleitetes Design.** Der Broker übernimmt die
Snapshot-Semantik und **verzichtet bewusst auf eine „für N Minuten
aufbewahren"-TTL**:

1. **Der Upstream ist die Wahrheit.** Eine erfolgreiche Antwort *ersetzt* den
   Snapshot der Quelle vollständig — abgeschlossene/stornierte Aufträge
   verschwinden sofort, weil sie einfach nicht mehr in der Antwort sind.
2. **Stale nur im Fehlerfall** (Quelle antwortet nicht *oder* ihr Breaker ist
   offen), begrenzt durch `cache_stale_max_s` (Default **120 s**, `0` = aus).
3. **Erledigte Schritte kommen nie aus dem Cache**: `cache_hide_completed`
   (Default an) filtert `(0040,0020)` = COMPLETED/DISCONTINUED aus
   Cache-Antworten. Live-Antworten werden durchgelassen — dort entscheidet das
   RIS (viele Häuser filtern selbst per `dcmHideSPSWithStatusFromMWL`).
4. **Begrenzt**: `cache_max_items` (Default 5000) plus automatischer Purge
   (2× Stale-Fenster).
5. **Optionaler Hintergrund-Refresh** je Quelle (`cache_refresh_s`, Default 0)
   für einen warmen Cache, damit die Überbrückung ab der ersten Sekunde greift.
6. **Sichtbar**: `served_stale` im Query-Log, Warnbanner im Dashboard,
   Health-Finding `cache_serving_stale`, Prometheus-Metriken.
7. **Löschkonzept (PHI)**: Der Payload enthält PHI (das ist der Zweck einer
   Worklist). Deshalb: nur in der internen DB, nie in Logs, die API liefert
   ausschließlich Metadaten (Accession, Study-UID, Modalität, Station,
   SPS-Status, Alter), automatischer Purge plus expliziter „Cache leeren"-Knopf.

**Backend.**

- Tabelle `worklist_cache` (Quelle, Dedupe-Key, Metadaten, DICOM-JSON-Payload,
  `fetched_at`), `cache.py` als einzige Schnittstelle.
- C-FIND-Pfad: Erfolg → `store_snapshot` (Snapshot-Ersetzung, Zähler für
  entfernte Einträge); Fehler oder offener Breaker → `stale_answers`, Ergebnis
  als `served_stale` im Query-Log, Status `partial`.
- Per-Quelle: `cache_stale_on_error`, `cache_refresh_s`. Global:
  `cache_enabled`, `cache_stale_max_s`, `cache_hide_completed`,
  `cache_max_items`.
- API: `GET /cache/stats`, `GET /cache/items`, `DELETE /cache`,
  `DELETE /cache/sources/{id}`.
- Metriken: `mwl_cache_entries`, `mwl_cache_age_seconds`, `mwl_cache_served_total`,
  `mwl_cache_refresh_total{result}`, `mwl_cache_dropped_total{reason}`.

**Frontend (OE3).**

- Cache-Karte im Dashboard: Einträge/Alter/Zustand je Quelle, Fallback-Flag,
  „Cache leeren" mit Bestätigung (auditiert).
- Warnbanner, solange der jüngste Query aus dem Cache bedient wurde.
- Query-Log markiert die betroffene Quelle als „aus Cache".
- Quellen-Dialog: Cache-Gruppe (Fallback-Schalter, Refresh-Intervall);
  die globalen Schalter erscheinen automatisch auf der Settings-Seite.

**Tests & Verifikation.** Snapshot-Ersetzung (Auftrag verlässt die Worklist →
Eintrag verschwindet), Stale-Fenster/Deaktivierung, Filter erledigter Schritte,
korrupte Payloads, Purge, Hintergrund-Refresh, DIMSE-Integration
(Quelle stirbt → Antwort aus dem Cache, `served_stale`, Status `partial`;
Breaker offen → Cache), API, UI (Karte, Banner, Dialog), E2E-Szenario im
Test-Stack (Quelle auf toten Port → Smoke liefert weiterhin Antworten).

**Risiken.** Der Cache enthält PHI → siehe Löschkonzept; ein zu langes
Stale-Fenster könnte erledigte Aufträge kurz wieder zeigen (deshalb Default
120 s + Filter); ein Hintergrund-Refresh erzeugt zusätzliche C-FIND-Last.

### P0-2 C-STORE-Spool mit Retry und Dead-Letter

**Wert in der Produktion.** Ist das Ziel-PACS nicht erreichbar, ist die Instanz
ohne Spool verloren: die Modalität bekommt einen Fehler und wiederholt in der
Regel nicht. Ein persistenter Spool mit Wiederholversuchen ist das klassische
„kein Bildverlust"-Versprechen kommerzieller Router (Laurel Bridge/Compass,
dcm4chee-Exporteure arbeiten genauso: lokal puffern, mit Backoff erneut senden).

**Speicherkonzept (entschieden).** Die Bytes liegen **auf Platte**, die
Metadaten in der Datenbank:

- `spool_dir` (Default `/var/lib/mwl-broker/spool`) ist ein eigenes Volume. Der
  Index, der die UI bedient, bleibt dadurch klein und schnell; das Spool-Volume
  bekommt seine eigene Größe, Backup- und Aufbewahrungsstrategie.
- **Datei-Lebensdauer**: eine Payload-Datei existiert nur, solange der Eintrag
  `queued`/`failed`/`dead` ist. Nach erfolgreicher Zustellung wird sie gelöscht
  — die Zeile bleibt `spool_retention_s` (Default 24 h) als **Duplikatsschutz**:
  dieselbe SOPInstanceUID wird nie zweimal gesendet.
- Geschrieben wird **atomar** (tmp → `fsync` → `rename`), damit ein Absturz nie
  eine halbe Datei hinterlässt.
- **Budget**: `spool_max_items` (Default 20000) und `spool_max_bytes`
  (Default 10 GiB). Ist es erschöpft, **weist der Broker ab**, statt still zu
  verwerfen: die Modalität bekommt einen Fehler (und wiederholt), der Betrieb
  sieht `spool_full` im Health-Panel und in den Metriken. Bilder werden nie
  heimlich verworfen.
- `accept_when_queued` (Default an): die Modalität bekommt **Erfolg**, sobald
  die Instanz sicher liegt. Das ist die klinisch richtige Antwort — nichts ist
  verloren, die Instanz ist eingereiht. Wer das nicht will (die Modalität soll
  erfahren, dass das PACS nicht erreicht wurde), setzt den Schalter aus; dann
  gilt die bisherige Policy (`strict_store_status`).
- **Dedupe in beiden Pfaden**: ein wiederholter C-STORE wird quittiert, ohne
  erneut zu senden (`spool.is_duplicate`) — sonst käme eine Instanz doppelt ins
  PACS, wenn sie zwischenzeitlich aus dem Spool zugestellt wurde.
- Nach `spool_max_attempts` (Default 10) wird der Eintrag zum **Dead Letter**:
  sichtbar in der Warteschlange, einzeln oder gesammelt wiederholbar,
  verwerfbar nur mit Begründung (auditiert).

**Backend.**

- Tabelle `store_spool` (Metadaten, `payload_path`, Status, `attempts`,
  `next_attempt_at`, `last_error`) + `spool.py` als einzige Schnittstelle.
- C-STORE-Pfad: Fehler → `spool.enqueue`; Ergebnis `queued`/`duplicate` +
  `accept_when_queued` → Erfolg an die Modalität, Store-Log `queued`.
- Retry-Worker im Lifespan (Intervall `spool_poll_s`), exponentieller Backoff
  (`spool_backoff_s * 2^(n-1)`, gekappt auf 1 h), Purge der zugestellten
  Einträge nach `spool_retention_s`.
- API: `GET /spool`, `GET /spool/stats`, `POST /spool/{id}/retry`,
  `POST /spool/retry-all`, `DELETE /spool/{id}?reason=` (Pflicht-Begründung).
- Metriken: `mwl_spool_items{status}`, `mwl_spool_oldest_seconds`,
  `mwl_spool_bytes`, `mwl_spool_queued_total{target}`,
  `mwl_spool_forwarded_total{target}`, `mwl_spool_dead_total{target}`.
- Health-Findings: `spool_dead_letters` (error), `spool_full` (error),
  `spool_backlog` (warning ab 15 min Rückstand).

**Frontend (OE3).**

- Spool-Karte im Dashboard: Rückstand, ältester Eintrag, Belegung, Dead-Letter-
  Badge, „Alle erneut senden" (bestätigt, auditiert), Link zur Warteschlange.
- Seite `/broker/spool`: Filter nach Status, Liste mit Ziel/Versuchen/Größe/
  letztem Fehler, „Jetzt erneut senden" je Eintrag, „Verwerfen" mit
  Pflicht-Begründung (Dialog erklärt, dass die Instanz verloren geht).
- Mobile: Einträge als Cards.

**Tests & Verifikation.** Enqueue/Dedupe/Budget/Ablehnung, atomares Schreiben,
Payload-Roundtrip, Backoff-Wachstum, Dead Letter nach n Versuchen, fehlendes
Ziel/unlesbare Datei, Retry/Retry-all/Discard/Purge, Worker-Stopp, API, UI;
Integration: C-STORE bei totem Ziel → `queued` + Erfolg an die Modalität → Ziel
gesund → Worker stellt zu (Instanz kommt wirklich an) → Wiederholung wird nicht
doppelt gesendet; E2E-Szenario im Test-Stack inklusive Dead Letter und
Retry über die UI.

**Risiken.** Speicherbedarf (Budget + Monitoring), Duplikatsschutz-Fenster
(`spool_retention_s` — danach wäre ein erneuter C-STORE wieder ein Neuzugang),
Dead Letters brauchen einen Betreiber, der sie ansieht (deshalb Health-Error).

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
- **Migrationen — umgesetzt (Sprint 4).** Statt der handgeschriebenen
  Spaltenliste gibt es jetzt **Alembic** mit Revisionspfad:
  `0001_baseline` wird nur *gestempelt* (das Basisschema kommt weiter aus den
  Modellen via `create_all`), `0002_cache_columns` und `0003_store_spool` sind
  die ersten echten Revisionen. `init_db()` = `create_all()` (fehlende Tabellen)
  - `alembic upgrade head` (geordnete Migrationen für bestehende Installationen).
  Jede Revision nach der Baseline ist **defensiv** (Existenzprüfung), weil eine
  frische Datenbank das aktuelle Schema bereits hat. Tests erzwingen den Pfad:
  eine DB ohne Versionstabelle wird gestempelt und migriert, Spalten kommen
  zurück, und jede Modellspalte über der Baseline hat eine Migration.
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
| 2 | Simulation (P1-2) + Config-Audit/Export/Rollback (P1-1) | keine | **✅ umgesetzt** |
| 3 | Worklist-Cache (P0-1) | Löschkonzept/PHI-Entscheidung | **✅ umgesetzt** |
| 4 | C-STORE-Spool (P0-2) | Alembic-Migration, Speicherkonzept | **✅ umgesetzt** |
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

### Sprint 2 — Simulation + Config-Audit/Export/Import/Rollback (umgesetzt)

**Backend.**

- `ConfigAudit`-Tabelle + `audit.py`: **jede** Konfigurationsmutation wird mit
  Before/After-Snapshot protokolliert (zentral in der API-Schicht, inklusive
  CRUD-Factory-Hooks). Actor aus `X-OE3-User` (Setting `audit_actor_header`),
  Correlation-ID aus `X-Request-Id`.
- `routing.py`: die Zielauflösung (seen_items → Regel → Default) ist aus
  `dimse` herausgezogen — **Echtbetrieb und Simulation nutzen dieselbe
  Funktion**, ein Dry-Run kann nicht driften (per Test abgesichert).
- `config_io.py`: Export als portables Dokument (`schema_version`, Regeln und
  Modify-Regeln referenzieren Quellen/Ziele **per Name**), Import als
  **Upsert-only** mit Dry-Run-Diff — nichts wird je implizit gelöscht.
  Ein Dokument darf die Knoten, auf die es verweist, selbst anlegen.
- `simulate.py`: `POST /simulate/route` und `POST /simulate/transform` liefern
  Entscheidung, Begründung, angewendete Regeln und den Tag-Diff.
- Rollback: `POST /config/rollback/{audit_id}` stellt den Zustand vor der
  Änderung wieder her (Update → zurücksetzen, Delete → neu anlegen,
  Create → entfernen) und protokolliert sich selbst.
- Neue Routen: `GET /audit/config`, `GET /config/export`,
  `POST /config/import?dry_run=`, `POST /config/rollback/{id}`,
  `POST /simulate/route`, `POST /simulate/transform` (Tags `audit`, `config`,
  `simulation`, vollständiger OpenAPI-Vertrag).

**Frontend (OE3).**

- Seite **`/broker/audit`** („Änderungsprotokoll"): Filter nach Objekttyp,
  Diff-Dialog (Feld/Vorher/Nachher), Rollback mit Bestätigung, Export als
  Datei-Download, Import mit **Pflicht-Dry-Run** (Diff + übersprungene
  Einträge sichtbar, erst dann „Import anwenden").
- **Fall prüfen (Simulation)** auf `/broker`: Accession/Study-UID plus
  optionale `Tag=Wert`-Zeilen → Routing-Entscheidung, angewendete Regeln,
  Tag-Diff und fehlschlagende Operationen.
- Mobile: Audit-Einträge als Cards; Schreibzugriffe (Rollback, Import) laufen
  über auditierte Mutations (`broker.config.*`).

**Tests & Verifikation.**

| Ebene | Umfang |
|---|---|
| pytest | 163 Tests, 97 % Coverage (+40: Audit je Mutation, Filter/Pagination, Rollback für Create/Update/Delete/Setting, Export/Import-Roundtrip, Idempotenz, Dry-Run ohne Schreibzugriff, Schema-Version, Simulation == Echtpfad) |
| vitest | 378 Tests, 98 % Broker-UI-Coverage (+30: Audit-Seite, Diff-Helfer, Fall-Prüfen-Panel, Audit-Hooks, Client) |
| Playwright | 31 Tests (Desktop + Mobile), inkl. Change-Log-Roundtrip (UI anlegen → Audit → Rollback → weg) und Fall-Prüfen |
| verify-ui.cjs | 66 Checks (Desktop 1400×900 + Mobile 375×812) |

**Nebenbefunde und behoben:** Import war für Dokumente, die ihre eigenen
Quellen mitbringen, fälschlich „übersprungen“; Operations wurden beim Import
mit `None`-Feldern normalisiert und damit nicht idempotent; `resourceId` im
Audit-Hook warf bei Dokumenten ohne Arrays.

### Sprint 3 — Worklist-Cache mit Stale-Fallback (umgesetzt)

**Recherche-Grundlage** (siehe Abschnitt P0-1): Medavis liefert Einträge bis
zum Abschluss im RIS; dcm4chee steuert den Lebenszyklus über HL7 ORM/MPPS und
blendet COMPLETED aus; der SPS-Status `(0040,0020)` ist der Standardmechanismus;
IHE trennt MWL (pull) und MPPS (push); kommerzielle Proxys (Flux Capacitor,
Laurel Bridge) cachen **Snapshots** mit begrenztem `ServeStaleForSeconds`.

**Umgesetzt.**

- `worklist_cache` + `cache.py`: Snapshot je Quelle, **ersetzt** bei jeder
  erfolgreichen Antwort (abgeschlossene Aufträge verschwinden sofort),
  DICOM-JSON-Payload via pydicom-Roundtrip.
- Stale-Fallback nur bei Fehler **oder offenem Breaker**, begrenzt durch
  `cache_stale_max_s` (Default 120 s); erledigte Schritte werden gefiltert.
- `served_stale` im Query-Log (neue Spalte + Migration), Status `partial`.
- Optionale Hintergrund-Aktualisierung (`cache_refresh_s` je Quelle) im
  Echo-Loop, automatischer Purge, `cache_max_items` als Schutz.
- API `GET /cache/stats|items`, `DELETE /cache[/sources/{id}]`; Metriken
  `mwl_cache_*`; Health-Finding `cache_serving_stale`.
- UI: Cache-Karte, Stale-Banner, Log-Badge, Cache-Gruppe im Quellen-Dialog,
  globale Schalter auf der Settings-Seite, i18n en/de.

**Tests & Verifikation.**

| Ebene | Umfang |
|---|---|
| pytest | 198 Tests, 97 % Coverage (+35: Snapshot-Semantik, Stale-Fenster, COMPLETED-Filter, korrupte Payloads, Purge, Refresh, DIMSE-Integration, API, Migration-Guard) |
| vitest | 386 Tests, 98 % Broker-UI-Coverage (+8: Cache-Karte, Stale-Banner, Dialog-Felder, Client) |
| Playwright | 35 Tests (Desktop + Mobile), inkl. Cache-Karte und Stale-Anzeige |
| test-stack.sh | Szenario „Quelle auf toten Port → Antwort aus dem Cache, Status partial" |
| verify-ui.cjs | 69 Checks (Desktop 1400×900 + Mobile 375×812) |

**Nebenbefund und behoben (produktionsrelevant):** Die neuen Spalten
(`mwl_source.cache_stale_on_error`, `cache_refresh_s`, `query_log.served_stale`)
fehlten in der Mini-Migration. Auf einer **bestehenden Postgres-Datenbank**
antwortete die API danach mit 500 — die SQLite-Tests erzeugen das Schema frisch
und konnten das nicht sehen; aufgefallen ist es beim Deep-Audit gegen den
echten Stack. Ergänzt, plus ein Test, der erzwingt, dass jede nachträglich
ergänzte Modellspalte eine Migration hat.

### Sprint 4 — C-STORE-Spool mit Retry/Dead-Letter (umgesetzt)

**Umgesetzt.**

- `store_spool` + `spool.py`: Store-and-Forward mit **Payload auf Platte**
  (atomar geschrieben), Metadaten in der DB, Budget (`spool_max_items`,
  `spool_max_bytes`) und **Ablehnung statt stillem Verwerfen**, wenn es voll ist.
- `accept_when_queued`: Erfolg an die Modalität, sobald die Instanz sicher
  liegt; abschaltbar (dann gilt `strict_store_status`).
- Retry-Worker im Lifespan mit exponentiellem Backoff, Dead Letter nach
  `spool_max_attempts`, Purge nach `spool_retention_s`.
- **Dedupe in beiden Pfaden** (`spool.is_duplicate`) — ein wiederholter C-STORE
  wird quittiert, ohne doppelt zu senden. (Beim Testen aufgefallen: ohne diese
  Prüfung kam eine Instanz, die zwischenzeitlich aus dem Spool zugestellt wurde,
  beim Wiederholen ein zweites Mal ins PACS.)
- API `GET /spool`, `GET /spool/stats`, `POST /spool/{id}/retry`,
  `POST /spool/retry-all`, `DELETE /spool/{id}?reason=` (Pflicht-Begründung,
  auditiert); Metriken `mwl_spool_*`; Health-Findings für Dead Letter, Voll und
  Rückstand.
- UI: Spool-Karte (Rückstand/Belegung/Retry-all) und Seite `/broker/spool`
  (Filter, Retry, Verwerfen mit Begründung), Mobile als Cards, i18n en/de.

**Alembic statt handgeschriebener Migrationen.** Siehe Querschnittsthema
„Migrationen": Baseline wird gestempelt, Revisionen sind defensiv, `init_db()`
führt `create_all` + `upgrade head` aus. Die Image-Build-Datei kopiert
`alembic.ini` und `migrations/` mit; `alembic` ist eine echte Dependency
(aufgefallen, weil der Container ohne sie unhealthy wurde — im venv war das
Paket nur manuell installiert).

**Tests & Verifikation.**

| Ebene | Umfang |
|---|---|
| pytest | 240 Tests, 97 % Coverage (+42: Spool-Unit, Integration, API, Health, Migrationspfad) |
| vitest | 395 Tests, 98 % Broker-UI-Coverage (+9: Spool-Karte, Warteschlange, Mobile, Client) |
| Playwright | 38 Tests (Desktop + Mobile), inkl. Dead Letter und Retry über die UI |
| test-stack.sh | Szenario „Ziel down → gepuffert → Ziel up → zugestellt" plus Dead Letter für die UI |
| verify-ui.cjs | 77 Checks (Desktop 1400×900 + Mobile 375×812) |

## Offene Entscheidungen (an den Betreiber)

1. **Cache und PHI — entschieden, aber bestätigen lassen:** Der Cache speichert
   Worklist-Daten (inkl. Patientennamen) für höchstens `cache_stale_max_s`
   (Default 120 s) in der internen DB. Kein Log, keine API-Exposition von
   Patientendaten, automatischer Purge, „Cache leeren" im UI, Stale nur im
   Fehlerfall. Wer das nicht möchte, setzt `cache_enabled = false` (dann
   antwortet der Broker im Fehlerfall leer) oder `cache_stale_max_s = 0`.
2. **Spool — entschieden, aber bestätigen lassen:** Payloads liegen auf einem
   eigenen Volume (`spool_dir`), Budget 20000 Einträge / 10 GiB, zugestellte
   Einträge bleiben 24 h als Duplikatsschutz. Wer mehr/weniger braucht, ändert
   `spool_max_items`, `spool_max_bytes`, `spool_retention_s` — oder schaltet den
   Spool mit `spool_enabled = false` ganz ab (dann gilt wieder striktes
   Fehlermelden an die Modalität).
3. **Audit-Actor:** kommt der Benutzerkontext aus einem vorgelagerten Proxy
   (Header) oder bleibt das Audit rein technisch?
4. **Alerting-Ziel:** Webhook (Teams/Slack) oder E-Mail/Syslog?
5. **TLS:** welche Strecken sind zu verschlüsseln (Modalität→Broker,
   Broker→PACS, beides)?
