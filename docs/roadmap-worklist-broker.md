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
vollständige Konfigurations-UI in OE3. **Stand der Umsetzung: alle P0-, P1- und
P2-Themen sind erledigt** (Sprints 1–8, siehe Umsetzungs-Log) plus die
UI-Härtung aus der [DAU-Gap-Analyse](ui-dau-gap-analysis.md) (Sprints 9–11),
die [MFA-Testumgebung](mfa-usability-test.md) und die i18n-Aufräumung.
Aktuelle Zahlen: 398 Backend-Tests (96 % Coverage), 490 Frontend-Tests,
55 Browser-E2E-Tests, 127 Checks im Deep-Audit.

---

## Status (Stand heute)

| Prio | Thema | Stand |
|---|---|---|
| P0 | Circuit Breaker, Health-Checks, Readiness | ✅ Sprint 1 |
| P0 | Worklist-Cache mit Stale-Fallback | ✅ Sprint 3 |
| P0 | C-STORE-Spool mit Retry/Dead-Letter | ✅ Sprint 4 |
| P1 | Simulation/Dry-Run, Config-Audit, Export/Import/Rollback | ✅ Sprint 2 |
| P1 | Alerting/Webhooks | ✅ Sprint 5 |
| P2 | Lokale Worklist + HL7-ORM, Stationsregeln, ATNA-Export | ✅ Sprint 6 |
| P2 | DICOM-TLS/mTLS + Zertifikatsverwaltung | ✅ Sprint 7 |
| – | RBAC, Aufbewahrung, flexibles Alerting | ✅ Sprint 8 |
| – | UI-Härtung (DAU), Eingabeführung, Bedienfluss | ✅ Sprints 9–11 |
| – | MFA-Testumgebung, Seiten-Hilfe, Entwürfe, i18n (9 Sprachen) | ✅ |

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
| **P1** | Alerting/Webhooks + Readiness-Endpoint | Betrieb erfährt Störungen, bevor Anwender anrufen | klein | **✅ Sprint 5** |
| **P2** | Lokale Worklist-Items / HL7-ORM-Adapter | Notfälle und ungeplante Untersuchungen | hoch | **✅ Sprint 6** |
| **P2** | Per-Station-Filter und -Priorität | jede Konsole sieht nur ihre Arbeitsliste | mittel | **✅ Sprint 6** |
| **P2** | DICOM-TLS (mTLS) + Zertifikatsverwaltung | Segmentierung/Netzwerkanforderungen | mittel | **✅ Sprint 7** |
| **P2** | ATNA-Audit-Export (syslog/TLS) | IHE-Compliance, zentrale Auditablage | mittel | **✅ Sprint 6** |

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

**Wert in der Produktion.** Der Betrieb soll es erfahren, bevor die Radiologie
anruft: ein RIS, das nicht mehr antwortet, ein PACS-Ausfall, ein Dead Letter im
Spool, ein Konfigurationsfehler.

**Backend.**

- `notify.py` mit einem **Ereigniskatalog** (9 Codes, per `GET /notify/events`
  abrufbar): `source_down`, `source_recovered`, `target_down`,
  `target_recovered`, `breaker_open`, `spool_dead_letter`, `spool_backlog`,
  `spool_full`, `config_error` — jeweils mit Severity und Beschreibung.
- **Zustellung ist fire-and-forget**: jeder Versand läuft auf einem kurzlebigen
  Hintergrund-Thread. Ein langsamer oder kaputter Webhook darf niemals einen
  C-FIND oder C-STORE verzögern; Fehler werden geloggt und gezählt, nie an den
  Aufrufer gereicht.
- **Dämpfung** je Ereignis+Objekt (`notify_min_interval_s`, Default 300 s):
  eine flappende Quelle erzeugt keine Nachrichtenflut. Der erste Check einer
  Quelle meldet nichts — gemeldet wird nur der **Übergang**.
- Payload ist Slack/Teams-kompatibel: ein `text`-Feld plus strukturierte Felder
  (`event`, `severity`, `message`, `details`, `broker`, `timestamp`).
- **Die Webhook-URL wird nie vollständig geloggt** (sie trägt in der Regel ein
  Secret-Token) — im Log steht nur `https://host/…`.
- Emit-Punkte: Echo-Loop (Übergänge up/down je Quelle/Ziel), Breaker (Öffnen),
  Spool (Dead Letter, Rückstand, voll), Echo-Loop alle 10 Ticks
  (Konfigurationsfehler).
- Settings: `notify_webhook_url` (leer = aus, muss http(s) sein),
  `notify_events` (CSV, gegen den Katalog validiert), `notify_min_interval_s`.
- API: `GET /notify/events`, `POST /notify/test` (auditiert) — der Testversand
  meldet das Ergebnis der Zustellung zurück.
- Metriken: `mwl_notify_sent_total{event}`, `mwl_notify_failed_total{event}`,
  `mwl_notify_suppressed_total{event}`.
- Readiness bleibt `GET /healthz/ready` (Sprint 1).

**Frontend (OE3).**

- Eigene **Alerting-Karte** auf der Settings-Seite (statt drei generischer
  Felder): Webhook-URL mit Override/Reset, **Ereignisauswahl als Checkboxen**
  (Code, Severity und Beschreibung kommen aus der API), Mindestabstand und
  **„Testnachricht senden"** mit Ergebnisanzeige — die Prüfung, die der
  Betreiber nach dem Einrichten braucht.

**Tests & Verifikation.** Ereigniskatalog, Abo-Logik, Validierung (URL,
unbekannte Codes), Zustellung gegen einen **echten lokalen HTTP-Empfänger**
(Payload-Form, `text`, Details), Dämpfung (gleiches Objekt unterdrückt, anderes
Objekt nicht, abschaltbar), unbekanntes Ereignis, Fehlerpfad (HTTP 500,
unerreichbar) ohne Wirkung auf den Broker, Testversand (ok/Fehler/keine URL),
URL-Redaction im Log, Übergangs-Alarme aus Echo/Breaker/Spool; API, UI.
Im Test-Stack läuft ein echter Empfänger auf dem Host
(`host.docker.internal`): der Smoke prüft den Testversand **und** dass echte
Ereignisse ankommen.

---

## P2 — Workflow-Erweiterungen

### P2-1 Lokale Worklist-Items / HL7-ORM-Adapter

**Wert in der Produktion.** Notfälle und ungeplante Untersuchungen existieren in
keinem RIS. Der Broker führt sie selbst und mischt sie in jede passende
C-FIND-Antwort — mit der **höchsten Priorität**, damit der Notfall gegen das RIS
gewinnt. Provenienz ist die Pseudo-Quelle `local`: sie wird nie abgefragt
(bleibt deaktiviert), ist aber in Routing-Regeln nutzbar — genau das schickt
Notfallbilder in ein anderes PACS.

**Backend.**

- Tabelle `local_worklist_item` (Zugang + Schritt-ID als Schlüssel, Patient,
  Modalität, Station, Termin, Gültigkeit, Herkunft `manual|hl7`) + `hl7_message`
  als Schnittstellen-Protokoll.
- `local_worklist.py`: DICOM-View (`to_dataset`), **Matching auf die
  Abfrageschlüssel** (Patient, Zugang, Modalität, Station, Datum — eine
  CT-Konsole sieht keine MR-Einträge), Merge als erste Quelle, Purge abgelaufener
  Einträge, `upsert_from_hl7`.
- `hl7.py`: ORM^O01-Parser. Die Feldzuordnung steht an einer Stelle und ist
  dokumentiert (inkl. der MSH-Besonderheit, dass MSH-1 das Trennzeichen selbst
  ist); unmappbare Felder landen in `warnings`, statt halbe Einträge zu erzeugen.
  Storni (`CA`/`OC`) löschen den Eintrag, Änderungen (`XO`/`SC`) aktualisieren,
  leere Felder überschreiben nie vorhandene Werte.
- `mllp.py`: **MLLP-Listener** (eigener Port, `0x0B … 0x1C 0x0D`-Framing) mit
  ACK/NAK — viele RIS sprechen nur MLLP. Er nutzt denselben Parser und
  Upsert-Pfad wie der REST-Weg.
- API: CRUD `/local-items`, `POST /hl7/orm?dry_run=` (Trockenlauf zeigt das
  Parse-Ergebnis und was passieren würde), `GET /hl7/messages`.
- Settings: `local_priority`, `local_default_validity_days`, `hl7_enabled`,
  `hl7_mllp_enabled|bind|port`, `hl7_default_station_aet|modality`.
- Metriken: `mwl_local_worklist_items`, `mwl_hl7_messages_total{transport,result}`.
- **PHI-Grenze:** Der Audit-/Export-Snapshot eines lokalen Eintrags enthält nur
  Termindaten, **keine Patientendaten** — sonst läge PHI im Änderungsprotokoll
  und damit im Konfigurations-Export. Ein Rollback stellt den Termin wieder her,
  nicht die Identität (der Diff zeigt das).

**Frontend (OE3).** Seite `/broker/worklist`: Tabelle (Mobile als Cards) mit
CRUD, Gültigkeit, Herkunft; daneben das **HL7-Panel** — Nachricht einfügen,
„Prüfen (Trockenlauf)" zeigt das Parse-Ergebnis samt Warnungen, „Anwenden"
schreibt, plus die letzten empfangenen Nachrichten.

**Tests & Verifikation.** Parser (Felder, Komponenten, Z-Segmente, Datums-/Zeit-
Formate, Storni, Müll-Eingaben, ACK), DICOM-View, Matching inkl. Wildcards,
Ablauf/Deaktivierung, Pseudo-Quelle erst bei Bedarf, HL7-Upsert (created/
updated/cancelled/cancel-unknown, kein Blanking, getrennte SPS-IDs), Purge,
Integration (lokaler Eintrag in der C-FIND-Antwort, Query-Filter, Dedupe-Vorrang,
Stationsregel verbirgt ihn), **MLLP end-to-end über einen echten Socket**, API, UI.
Im Test-Stack: Notfall anlegen → erscheint in der C-FIND-Antwort, HL7
Trockenlauf + Anwenden, MLLP-Listener.

### P2-2 Per-Station-Filter und -Priorität

**Wert in der Produktion.** Jede Konsole soll ihre Arbeitsliste sehen. Eine
Station-Regel verbirgt Quellen vor einer Konsole (`deny`) oder zeigt nur
bestimmte (`allow`) und kann die **Merge-Reihenfolge** für diese Konsole
umdrehen — damit gewinnt z. B. das Notfall-RIS am CT, das Routine-RIS am
Röntgen.

**Backend.**

- Tabelle `station_rule`: `station_aet` (`*` = Rückfall), `mode`
  (`allow|deny`), `source_ids`, `source_priority` (`{source_id: priority}`),
  `priority`, `enabled`.
- `station_rules.py`: Matching (exakte Station vor Rückfall, erste aktive Regel
  nach `priority`), Sichtbarkeit, Umsortierung der Fan-out-Quellen und
  **Filterung nach dem Merge** — die Deduplizierung darf nicht von der Station
  abhängen (gleicher Zugang ⇒ ein Eintrag, egal wer fragt).
- `query_station()` liest den `ScheduledStationAETitle` aus der SPS-Sequenz
  (mit Rückfall auf die oberste Ebene). Ohne Station greift keine Regel.
- API: CRUD `/station-rules`, `POST /simulate/station` (Vorschau: welche Quellen
  sichtbar, welche effektive Priorität, welche Regel — dieselbe Logik wie im
  Echtpfad).
- Validierung: `mode` als Enum, `station_aet` gegen das AE-Titel-Muster
  (Tippfehler würden sonst still nie greifen).

**Frontend (OE3).** Seite `/broker/stations`: Regel-CRUD mit Quellen-Auswahl als
Checkboxen, Modus-Umschalter und **Vorschau-Panel** („Welche Quellen sieht diese
Konsole?") — per Knopf oder direkt aus der Regelzeile.

**Tests & Verifikation.** Matching (exakt/Rückfall/deaktiviert/Reihenfolge),
Sichtbarkeit (deny/allow/leere allow-Liste), Prioritäts-Override,
Merge-Filterung, Vorschau; Integration: C-FIND mit Stations-AET liefert
gefilterte Antworten, andere Stationen bleiben unberührt, Prioritäts-Override
dreht die Dedupe **inklusive der `seen_items`-Provenienz**; API inkl. Validierung
und Audit; UI (Desktop + Mobile); Test-Stack: Regel anlegen und Vorschau prüfen.

### P2-3 DICOM-TLS (mTLS) und Zertifikatsverwaltung

**Wert in der Produktion.** Verschlüsselte Strecken sind heute nicht nötig (LAN,
VPN, direkte IPs/Ports) — für die Zukunft aber unvermeidlich. Deshalb ist alles
**standardmäßig aus** und wird pro Richtung eingeschaltet, ohne den Bestand zu
berühren.

**Zwei Richtungen, getrennt schaltbar.**

- **Eingehend** (`tls_inbound_*`): ein **zweiter Listener** auf eigenem Port
  (Default 2762) neben dem Klartext-Port. Das ist die Voraussetzung für eine
  **stufenweise Umstellung**: eine Modalität nach der anderen, die übrigen
  laufen unverändert weiter. `tls_inbound_client_auth` schaltet mTLS
  (`none|optional|required`); bei `optional`/`required` ist eine CA-Datei
  Pflicht — sonst würde der Broker jede Modalität abweisen.
- **Ausgehend** (`tls_outbound_*` + **je Quelle/Ziel** `tls`/`tls_verify`):
  Der Broker verifiziert RIS/PACS-Zertifikate gegen eine CA (leer =
  System-Truststore) und kann sich per Client-Zertifikat ausweisen (mTLS).
  `tls_verify=false` ist ein **bewusster** Ausnahmeschalter für ein
  selbstsigniertes Testsystem und wird im Health-Panel als Warnung geführt.

**Für Betreiber, die nicht in der Materie stecken.**

- **Zertifikat selbst erzeugen** (`POST /tls/self-signed` + Dialog): Common Name,
  Gültigkeit, SANs (IPs/Hostnamen), optional als CA. Der öffentliche Teil wird
  angezeigt und an den Lieferanten weitergegeben; der private Schlüssel wird mit
  Modus 0600 geschrieben und **nie über die API ausgegeben**.
- **Zustandsübersicht** (`GET /tls/overview` + Karte): existiert die Datei, ist
  sie lesbar, wem gehört sie, wann läuft sie ab, passt der Schlüssel zum
  Zertifikat, ist der Schlüssel für andere lesbar — in Klartext.
- **Endpunkt prüfen** (`POST /tls/test` + Knopf): echter TLS-Handshake mit
  Protokoll, Cipher, Peer-Subject/Issuer/Ablauf und optional einem **C-ECHO über
  TLS**. Fehlermeldungen sagen, was zu tun ist („Zertifikat in die CA-Datei
  importieren oder 'prüfen' für diesen Knoten abschalten").
- **Ablaufüberwachung**: Health-Findings (`tls_certificate_expiring` ab 30 Tagen,
  `tls_certificate_expired`), Metrik `mwl_tls_certificate_days_left`, neues
  Alerting-Ereignis `tls_certificate_expiring` sowie Warnungen für
  `tls_verification_disabled`, `tls_key_world_readable`, `tls_key_mismatch` und
  unvollständige Konfigurationen.

**Backend.** `tls.py` (Kontexte für Server/Client, Inspektion, Erzeugung,
Endpunkt-Check), `ssl_context` am zweiten pynetdicom-Listener, `tls_args` an
allen ausgehenden Assoziationen (C-FIND, C-ECHO, C-STORE inkl. Spool-Worker),
Alembic-Revision `0006` für die Knoten-Felder, Settings mit den Validierungsarten
`enum` und `path`, `cryptography` als Dependency (auch für pynetdicom-TLS).

**Tests & Verifikation.** Kontexte (Server/Client, Verify-Modi, mTLS-Pflicht),
Zertifikatsinspektion (Ablauf, SANs, CA-Flag, Schlüssel-Modus, Schlüssel/
Zertifikat-Zuordnung), Erzeugung (0600, PEM, SANs), Übersicht, Endpunkt-Check
gegen einen **echten TLS-Server** (Handshake, Peer-Zertifikat, Verifikation mit
und ohne CA, mTLS mit Client-Zertifikat, unerreichbarer Port); Integration mit
**echten DICOM-TLS-Assoziationen**: C-FIND über den TLS-Listener, mTLS
(ohne Zertifikat abgewiesen, mit Zertifikat angenommen), ausgehender C-FIND über
TLS (inkl. Fehlschlag ohne CA), C-ECHO und C-STORE über TLS, Durchreichen der
Knoten-Flags aus der Datenbank; Health-, API- und UI-Tests. Im Test-Stack:
Zertifikat erzeugen, Listener aktivieren, **C-FIND über TLS mit
CA-Verifikation**, Endpunkt-Check (TLSv1.3 + C-ECHO).

**Risiken.** Ein falsch gesetztes `tls_verify=false` schwächt die
Authentifizierung (deshalb Warnung + Health-Finding); abgelaufene Zertifikate
legen die Strecke lahm (deshalb Ablaufüberwachung und Alerting); die
Klartext- und die TLS-Strecke existieren parallel, solange nicht alle Geräte
umgestellt sind (bewusst, für die Migration).

### P2-4 ATNA-Audit-Export (IHE, syslog/TLS)

**Wert in der Produktion.** IHE verlangt eine zentrale, manipulationssichere
Nachvollziehbarkeit: wer hat wann welche Patientendaten abgefragt oder
weitergeleitet. Der Broker erzeugt die Nachrichten, die Gegenstelle
(Audit Record Repository) betreibt das Haus selbst — hier zunächst als eigene
Instanz.

**Backend.**

- `atna.py`: **DICOM PS3.15 / RFC 3881 Audit Messages** als XML, verpackt in
  einen **RFC 5424 Syslog-Frame** (mit der von DICOM geforderten UTF-8-BOM),
  Transport **TCP oder TLS** (optional mit CA-Bundle zur Verifikation).
- Ereignisse: `Query` (110112, ein C-FIND mit den offengelegten Patienten),
  `Import` (110104) und `Export` (110106) je C-STORE, `Security Alert` (110113)
  bei abgewiesener Assoziation (mit `EventOutcomeIndicator=8`).
- **Zustellung blockiert nie den DICOM-Pfad**: eine begrenzte Queue
  (`atna_queue_max`) mit Worker-Thread; ist sie voll, werden Nachrichten
  verworfen und gezählt (`mwl_atna_dropped_total`). Ein kurzer Config-Cache (2 s)
  hält die „ist Audit aktiv?"-Prüfung von der Datenbank weg.
- **Bewusst opt-in**: `atna_enabled` ist per Default aus — Audit-Daten verlassen
  den Broker erst, wenn das eingeschaltet wird.
- API: `GET /atna/stats`, `POST /atna/test` (synchron, meldet das Ergebnis),
  `GET /atna/sample` (Beispielnachricht — das Erste, was das ARR-Team braucht).
- Metriken: `mwl_atna_sent_total{event}`, `mwl_atna_failed_total`,
  `mwl_atna_dropped_total`, `mwl_atna_queue_size`.
- **PHI:** Eine Audit-Nachricht enthält die Patienten-ID (das ist ihr Zweck) —
  sie geht an die Gegenstelle des Hauses, **nicht** in die Broker-Logs.

**Frontend (OE3).** ATNA-Karte auf der Settings-Seite: Zustand (aus/konfiguriert,
Pufferstand), Ein/Aus, Host/Port/Transport/CA, **Testversand mit Ergebnis** und
die **Beispielnachricht** als XML zum Anzeigen.

**Tests & Verifikation.** Aufbau der Nachricht (Event-Codes, Rollen, Patient/
Study/Zugang/Query-Objekte, XML-Escaping), Syslog-Frame (PRI, RFC-5424-Kopf,
BOM), **Zustellung an einen echten TCP-Empfänger**, TLS-Zweig mit CA-Verifikation
(monkeypatch), bounded Queue inkl. Drop-Metrik, Fehlerpfade, Testversand,
`stats`; Integration: C-FIND erzeugt Query-Audits (inkl. je Patient), C-STORE
erzeugt Import+Export, abgewiesene AET erzeugt ein Security-Event, ohne
Konfiguration passiert nichts; API + Validierung; UI. Im Test-Stack läuft ein
**echter Syslog-Empfänger auf dem Host**: Testnachricht **und** die während der
Szenarien anfallenden Audit-Nachrichten (Query-Events) kommen an.

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
| 5 | Alerting (P1-4), dann P2 nach fachlicher Priorisierung | Betriebsentscheidung | **✅ umgesetzt** |

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

### Sprint 5 — Alerting/Webhooks (umgesetzt)

**Umgesetzt.**

- `notify.py`: Ereigniskatalog (9 Codes) + `GET /notify/events`; Zustellung als
  JSON-POST auf einem Hintergrund-Thread (DICOM-Pfad wird nie blockiert);
  Dämpfung je Ereignis+Objekt; Slack/Teams-kompatibler Payload; URL-Redaction
  im Log; `POST /notify/test` mit Ergebnis.
- Emit-Punkte: Echo-Übergänge (Quelle/Ziel up/down), Breaker-Öffnen,
  Spool-Dead-Letter/-Rückstand/-voll, Konfigurationsfehler aus dem Echo-Loop.
- Settings `notify_webhook_url` / `notify_events` / `notify_min_interval_s`
  (neue Validierungs-Kinds `url` und `events`), Metriken `mwl_notify_*`.
- UI: Alerting-Karte auf der Settings-Seite mit Ereignis-Checkboxen und
  Testversand (die drei Keys erscheinen nicht mehr in der generischen Liste).
- Deployment: `host.docker.internal:host-gateway` für den Broker, damit ein
  Webhook auf dem Host erreichbar ist.

**Tests & Verifikation.**

| Ebene | Umfang |
|---|---|
| pytest | 260 Tests, 97 % Coverage (notify.py 100 %; +20: Katalog, Abo, Dämpfung, Zustellung gegen echten Empfänger, Fehlerpfade, Redaction, Übergangs-Alarme) |
| vitest | 404 Tests, 98 % Broker-UI-Coverage (+9: Alerting-Karte, Client) |
| Playwright | 40 Tests (Desktop + Mobile), inkl. Testversand aus der UI |
| test-stack.sh | Echter Webhook-Empfänger auf dem Host: Testnachricht **und** echte Ereignisse (`breaker_open`, `config_error`, `spool_dead_letter`) kommen an |
| verify-ui.cjs | 80 Checks (Desktop 1400×900 + Mobile 375×812) |

### Sprint 6 — P2: lokale Worklist/HL7, Stationsregeln, ATNA (umgesetzt)

**Umgesetzt.** Die drei fachlich priorisierten P2-Themen (P2-1, P2-2, P2-4) —
jeweils Backend, API, DAU-sichere OE3-Oberfläche, Tests und Verifikation:

- **P2-1** `local_worklist_item` + `hl7_message` + `hl7.py` + `mllp.py`:
  Notfall-Einträge mit höchster Merge-Priorität, Matching auf die
  Abfrageschlüssel, Pseudo-Quelle `local` (routingfähig), HL7-ORM-Parser mit
  Trockenlauf und MLLP-Listener, Seite `/broker/worklist` mit HL7-Panel.
- **P2-2** `station_rule` + `station_rules.py`: Sichtbarkeitsfilter und
  Prioritäts-Override je Konsole, Filterung nach dem Merge, Vorschau-Endpunkt,
  Seite `/broker/stations`.
- **P2-4** `atna.py`: PS3.15-Audit-Nachrichten als RFC-5424-Syslog über TCP/TLS,
  bounded Queue, Testversand, Beispielnachricht, ATNA-Karte auf der
  Settings-Seite. Bewusst opt-in.

**Beim Umsetzen gefunden und behoben.**

| Fund | Fix |
|---|---|
| HL7-Feldindizes waren durchweg um eins verschoben (MSH-1 *ist* das Trennzeichen, alle anderen Segmente sind 1-basiert) | Parser auf **HL7-Feldnummern** umgestellt (`_field(seg, 9, msh=True)`), Testnachrichten korrigiert |
| Uhrzeit aus einem kombinierten `YYYYMMDDHHMM`-Feld wurde als `20:26` gelesen | `_format_time` unterscheidet jetzt Zeit-only (HHMM) und vollen Stempel |
| Die Pseudo-Quelle `local` wurde bei **jedem Start** angelegt und tauchte in einer frischen Installation als Quelle auf | entsteht erst mit dem ersten lokalen Eintrag (`answers_for` bricht ohne Einträge vorher ab) |
| Der Audit-Snapshot lokaler Einträge enthielt den **Patientennamen** — damit PHI im Änderungsprotokoll und im Konfigurations-Export | Snapshot auf Termindaten reduziert, dokumentiert; ein Rollback stellt den Termin, nicht die Identität wieder her |
| `audit.snapshot()` warf bei `None` (Storno ohne Zeile) | akzeptiert `None` (Dokumentation war schon so) |
| HL7-Nachrichten wurden nur im MLLP-Pfad protokolliert | Logging ins gemeinsame `upsert_from_hl7` gezogen |
| Test-Stack behielt seine Volumes → Restdaten machten die Assertions vom Vorlauf abhängig | `down -v` vor dem Start; die neuen Abschnitte sind zusätzlich idempotent |

**Tests & Verifikation.**

| Ebene | Umfang |
|---|---|
| pytest | 339 Tests, 96 % Coverage (+36: Parser, lokale Items, MLLP über echten Socket, Stationsregeln, ATNA) |
| vitest | 428 Tests, 98 % Broker-UI-Coverage (+24: Worklist-/Stationsseite, ATNA-Karte, Client) |
| Playwright | 44 Tests (Desktop + Mobile), inkl. Notfall in der Liste, HL7-Trockenlauf, Stationsvorschau, ATNA-Beispielnachricht + Testversand |
| test-stack.sh | Notfall erscheint in der C-FIND-Antwort, HL7 Trockenlauf/Anwenden, Stationsvorschau, **echter Syslog-Empfänger** mit Audit-Nachrichten (42, Query-Events enthalten) |
| verify-ui.cjs | 100 Checks (Desktop 1400×900 + Mobile 375×812) |

### Sprint 7 — DICOM-TLS/mTLS + Zertifikatsverwaltung (umgesetzt)

**Umgesetzt.**

- `tls.py`: Server-/Client-Kontexte (TLS ≥ 1.2, mTLS `none|optional|required`),
  Zertifikats- und Schlüsselinspektion, Erzeugung selbstsignierter Zertifikate
  (0600, SANs, optional CA), Endpunkt-Check mit echtem Handshake und optionalem
  C-ECHO, Ablauf- und Konfigurationsdiagnose.
- **Zweiter Listener** für eingehendes TLS (`tls_inbound_port`, Default 2762)
  neben dem Klartext-Port — stufenweise Umstellung pro Modalität.
- **Je Knoten** `tls`/`tls_verify` für Quellen und Ziele (Alembic `0006`),
  globale Trust-/Identitätsdateien für ausgehend, `tls_args` an C-FIND, C-ECHO
  und C-STORE (auch im Spool-Worker).
- API `GET /tls/overview`, `POST /tls/self-signed`, `POST /tls/test`
  (auditiert); Health-Findings und Alerting-Ereignis für Ablauf/Fehlkonfiguration;
  Metriken `mwl_tls_*`.
- UI: **TLS-Karte** (Listener, mTLS, Zertifikate mit Ablauf-Badges, Erzeugungs-
  dialog mit PEM-Anzeige, Endpunkt-Prüfung) und eine TLS-Gruppe im Quellen-/
  Ziel-Dialog. Defaults: alles aus, Verifikation an.

**Beim Umsetzen gefunden und behoben.**

| Fund | Fix |
|---|---|
| Ausgehendes TLS scheiterte, weil `tls_args` ohne Server-Namen kam (Python verweigert die Hostnamen-Prüfung ohne Namen, SNI fehlt) | `client_tls_args(..., server_name=host)`; der Host wird an allen Aufrufen durchgereicht |
| Bei `verify=false` liefert Python **kein** Peer-Zertifikat — die Prüfung zeigte nichts an | Peer-Zertifikat als DER holen und selbst parsen (funktioniert in beiden Modi) |
| `overview()` listete per Operator-Präzedenz auch nicht konfigurierte CA-Einträge | Liste über die Rollen gefiltert |
| Die neuen TLS-Felder fehlten im Audit-Serializer → Konfigurations-Import war nicht mehr idempotent | Felder ergänzt (Contract-Test aktualisiert) |
| TLS-Endpunkte und Health-Checks lasen den 2-s-Settings-Cache → Änderungen wirkten verzögert | `tls.reload()` in den Endpunkten und im Health-Check |
| Der Endpunkt-Check im Test-Stack prüfte den Host-Port statt des Container-Ports | interner Port (der Broker prüft seinen eigenen Listener) |
| `cryptography` fehlte in den Dependencies → Container unhealthy | als Dependency ergänzt (`cryptography>=42,<51`) |

**Tests & Verifikation.**

| Ebene | Umfang |
|---|---|
| pytest | 377 Tests, 96 % Coverage (tls.py 95 %; +38: Kontexte, Inspektion, Erzeugung, Endpunkt-Check, echte TLS-Assoziationen, Health, API) |
| vitest | 435 Tests, 98 % Broker-UI-Coverage (+7: TLS-Karte, Client) |
| Playwright | 46 Tests (Desktop + Mobile), inkl. Zertifikatsliste und Endpunkt-Check über die UI |
| test-stack.sh | Zertifikat erzeugen → Listener aktiv → **C-FIND über TLS mit CA-Verifikation** → Endpunkt-Check `TLSv1.3` + C-ECHO |
| verify-ui.cjs | 104 Checks (Desktop 1400×900 + Mobile 375×812) |

### Sprint 8 — Betreiberentscheidungen umsetzbar gemacht (umgesetzt)

Die vier offenen Betreiberentscheidungen sind jetzt **konfigurierbar und
sichtbar** statt offen:

**RBAC (brokerRead/brokerWrite).** `rbac_mode` (`off|enforce`, Default off),
`rbac_roles_header` (Default `X-OE3-Roles`) und `rbac_write_role` (Default
`brokerWrite`). Im Modus `enforce` braucht jeder Nicht-GET-Request die Rolle im
Rollen-Header; Lesen bleibt offen (der Proxy authentifiziert bereits). Die UI
fragt `GET /rbac/status` ab und zeigt ein Banner, wenn der Anwender nur lesen
darf — statt ihn in 403er laufen zu lassen. Im Test-Stack: Schreiben ohne Rolle →
403, mit Rolle → 201, Status-Endpunkt meldet `enforced=True can_write=False`.

**Retention/Löschkonzepte.** Pro Tabelle konfigurierbar (Tage, `0` = für immer):
Query-Log (90), Store-Log (90), HL7-Nachrichten (30), Spool-Einträge (7), lokale
Einträge (0 = nur die eigene Gültigkeit), Änderungsprotokoll (0 = für immer —
das Rechnungslegungsarchiv). `retention.py` als einzige Schnittstelle: Übersicht
(Zeilen, ältester Eintrag, was ein Aufräumen jetzt löschen würde), Purge (per
API auditiert), periodischer Lauf im Echo-Loop, Metrik
`mwl_retention_oldest_seconds{table}`. UI: **Retention-Karte** mit den
Tabellen, „für immer" ausdrücklich als Text, „Jetzt aufräumen" mit
Bestätigung und Ergebnis. Die Worklist-Cache ist bewusst **nicht** Teil davon —
sie hat ihren eigenen, viel kürzeren Lebenszyklus (Stale-Fenster + „Cache
leeren").

**Alerting-Ziel flexibel:** `notify_webhook_url` akzeptiert jetzt **mehrere
Ziele** (Komma-getrennt) — z. B. Teams **und** ein Syslog-Konverter parallel.
Die Zustellung läuft fire-and-forget an alle Ziele; der Testversand meldet das
Ergebnis je Ziel. E-Mail/Syslog bleibt über einen Konverter-Dienst lösbar
(dokumentiert).

**TLS-Rollout-Reihenfolge** ist ein Ablauf, kein Code — als Runbook im
Roadmap-Abschnitt P2-3 dokumentiert (zweiter Listener → Zertifikat erzeugen →
Endpunkt-Prüfung → eine Modalität nach der anderen umstellen → Klartext-Port
abschalten).

**Beim Umsetzen gefunden und behoben.**

| Fund | Fix |
|---|---|
| Die Settings-Datei hatte durch die Patches verunglückte Blöcke (`local_priority` mit TLS-Beschreibung, Beschreibungs-Tupel in `_INT_RANGES`) | `KNOWN` und `_INT_RANGES` **kanonisch neu aufgebaut** (alle 60 Schlüssel, korrekte Arten, Bereiche) |
| `retention_spool_days_days` (Tippfehler) | auf `retention_spool_days` korrigiert |
| Der RBAC-Reset im Test-Stack nutzte `DELETE` — das ist selbst ein Write und wurde abgewiesen | Reset über `PUT` mit der Write-Rolle |
| `retention.purge()` lief nicht über die API → kein Audit-Eintrag | der Test führt die Aktion über den Endpunkt (der auditiert) |

**Tests & Verifikation.**

| Ebene | Umfang |
|---|---|
| pytest | 392 Tests, 96 % Coverage (+15: RBAC-Policy und -Enforcement, Retention-Übersicht/Purge/Metriken, Multi-Webhook) |
| vitest | 441 Tests, 98 % Broker-UI-Coverage (+6: Retention-Karte, RBAC-Banner) |
| Playwright | 48 Tests (Desktop + Mobile), inkl. Retention-Karte und RBAC-Banner |
| test-stack.sh | RBAC: Schreiben ohne Rolle → **403**, mit Rolle → **201**, Status-Endpunkt meldet `can_write=False` für den Read-only-Aufrufer |
| verify-ui.cjs | 109 Checks (Desktop 1400×900 + Mobile 375×812) |

## Offene Entscheidungen (an den Betreiber)

1. **RBAC — umsetzbar gemacht (Sprint 8):** `rbac_mode=enforce` schaltet die
   Trennung scharf; der Proxy übergibt die Rollen im Header
   (`rbac_roles_header`), und die Rolle `rbac_write_role` (Default
   `brokerWrite`) darf die Konfiguration ändern. Lesen bleibt offen — der Proxy
   authentifiziert bereits. Die UI zeigt Lesern einen Banner und deaktiviert die
   Schreibaktionen, statt sie in 403er laufen zu lassen. Default: aus.
2. **Retention — umsetzbar gemacht:** Pro Tabelle konfigurierbar (Query-Log 90,
   Store-Log 90, HL7 30, Spool 7, lokale Einträge nur über ihre eigene
   Gültigkeit, Änderungsprotokoll 0 = für immer). Übersicht + manuelles
   Aufräumen in der UI; nichts wird implizit gelöscht.
3. **Alerting-Ziel — flexibel:** mehrere Webhook-Ziele (Komma-getrennt) werden
   parallel beliefert; E-Mail/Syslog über einen kleinen Konverter-Dienst davor.
4. **TLS-Rollout — Runbook statt Code:** der zweite Listener + die Knoten-
   Schalter erlauben die stufenweise Umstellung; das Vorgehen ist in P2-3
   dokumentiert.
