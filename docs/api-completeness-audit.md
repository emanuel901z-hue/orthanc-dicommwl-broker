# API-Vollständigkeitsprüfung (Broker-REST + DICOM)

Stand: 21.09.2026 · geprüft gegen den **laufenden** Broker (v1.0.0, `GET /openapi.json`)
und den Code in `mwl-broker/` + `orthanc-explorer-3-usable/`.

Diese Prüfung ist **gemessen**, nicht geschätzt: Routen aus der ausgelieferten
OpenAPI-Spezifikation, Aufrufe aus dem typisierten Client
(`src/api/broker.ts`), Treffer in den Testdateien, Aussagen der Dokumente,
Metriknamen aus `/metrics`, DICOM-Kontexte aus `dimse.py` — plus Live-Aufrufe
gegen den Stack.

## 1. Was vollständig ist (mit Belegen)

| Prüfung | Ergebnis |
|---|---|
| **Kein UI-Aufruf ohne Route** | 63 Aufrufe im Client, **0** ohne passende Backend-Route (drei Scheintreffer waren Regex-Artefakte und wurden einzeln widerlegt) |
| **Keine tote Route** | 66 Routen; nur `/healthz`, `/healthz/ready`, `/metrics` werden von der UI nicht aufgerufen — das ist deren Zweck (Monitoring) |
| **CRUD je Ressource** | `sources`, `targets`, `rules`, `transforms`, `station-rules`, `local-items` haben vollständiges GET/POST/PUT/DELETE; `settings` GET/PUT/DELETE (PUT = Upsert) |
| **Tests je Route** | jede Route hat Treffer in `tests/` bzw. E2E; vier Scheinlücken waren f-String-Artefakte (`/sources/{id}/echo` etc. sind getestet) |
| **Audit bei Konfigmutationen** | alle `POST/PUT/DELETE` auf Konfigurationsobjekte schreiben einen Änderungsprotokoll-Eintrag — **inklusive Import** (`config_io` protokolliert je Element: `import.source`, `import.target`, `import.rule`, `import.transform`, `import.setting`) |
| **Metriken** | 45 Metrikfamilien: C-FIND (Dauer, Antworten je Quelle), C-STORE, Spool, Cache, Breaker, ATNA (gesendet/fehlgeschlagen/verworfen), Alerting, Retention-Alter, TLS-Restlaufzeit, Konfig-Findings |
| **Health** | `/healthz` (liveness) + `/healthz/ready` (`{"ready":true,"checks":{"db":true,"scp":true}}`) + `/api/v1/health/config` (Konfigurationskonsistenz) |
| **DICOM-Schnittstelle** | MWL **C-FIND**, **C-STORE**, **C-ECHO** (SCP+SCU), DICOM-TLS/mTLS eingehend (zweiter Listener) und ausgehend je Knoten |
| **Fehlerform** | überall `{"detail": …}` — Klartext bei eigenen Prüfungen, `{loc,msg,type}`-Liste bei Schemafehlern; dokumentiert im Info-Block der Spezifikation |

## 2. Befunde

### A1 — RBAC sperrt die **Nur-Lese**-Diagnose (P1) — **behoben**

In `rbac_mode=enforce` blockt die Middleware **jeden** Nicht-GET unter
`/api/v1` ohne Schreibrolle (`main.py`, Middleware). Damit sind auch die
Werkzeuge gesperrt, die **nichts verändern**:

| Route | Wirkung | Live gemessen (ohne Rolle) |
|---|---|---|
| `POST /simulate/route`, `/station`, `/transform` | Trockenlauf | **403** |
| `POST /sources/{id}/echo`, `/targets/{id}/echo` | C-ECHO-Prüfung | **403** |
| `POST /tls/test` | Handshake-Prüfung | **403** |
| `POST /hl7/orm?dry_run=true`, `POST /config/import?dry_run=true` | Trockenlauf | **403** |

Die **UI bietet diese Knöpfe einem Nur-Leser unverändert an** (`CaseCheckPanel`
prüft `can_write` nicht) → der Anwender läuft in einen 403, obwohl er nur
nachsehen wollte. Genau die sichersten Werkzeuge sind also für die
zurückhaltenden Rollen unbenutzbar.

**Fix:** Absicht statt Methode prüfen — eine kleine Allowlist
(`simulate/*`, `*/echo`, `tls/test`) plus die Bedingung `dry_run=true` für
`hl7/orm` und `config/import`. `atna/test` und `notify/test` bleiben geschützt
(sie lösen echte Nachrichten aus) — die blendet die UI dann für Nur-Leser aus.

### A2 — Cache-Leeren wird nicht protokolliert (P1) — **behoben**

`DELETE /api/v1/cache` und `DELETE /api/v1/cache/sources/{id}` löschen den
Arbeitslisten-Cache — also **die Ausfallüberbrückung**, die die Modalitäten
während eines RIS-Ausfalls bedient. Beide Endpunkte schreiben **keinen**
Änderungsprotokoll-Eintrag (im Handler steht nur `cache.clear(...)`).
Nachvollziehbar ist hinterher nicht, wer die Überbrückung abgeschaltet hat.

**Fix:** `audit.record` in beiden Handlern (Aktion `cache.clear`,
`cache.clear_source`).

### A3 — Breaker-Reset ohne Spur (P2) — **behoben**

`POST /sources/{id}/reset-breaker` schließt den Circuit Breaker einer Quelle —
also die Entscheidung, ein als gestört erkanntes System wieder zu befragen.
Der Handler ruft nur `breaker.reset(source_id)`: kein Protokolleintrag, keine
Logzeile.

**Fix:** Protokolleintrag (Aktion `breaker.reset`) + Logzeile.

### A4 — `GET /status` kennt keine Version (P2) — **behoben**

Der Status liefert `counts`, `db_ok`, `scp_listening`, `sources`, `targets` —
aber **keine Version und keine Laufzeit**. „Welcher Stand läuft hier?" ist per
API und in der Oberfläche nicht beantwortbar (nur über `/openapi.json`).

**Fix:** `version` (aus `pyproject`/`__init__`) und `started_at`/`uptime_s`
ergänzen; die UI zeigt es in der Kopfzeile/Überblickskarte.

### A5 — Paginierung inkonsistent (P2) — **behoben**

| Liste | Parameter | Tiefe erreichbar? |
|---|---|---|
| `logs/queries`, `logs/stores`, `audit/config` | `limit`, `offset` | ja |
| `spool`, `hl7/messages`, `cache/items` | nur `limit` | **nein** |

Beim Spool (Budget 20 000 Einträge) und bei 30 Tagen HL7-Nachrichten sieht man
damit **immer nur die neuesten N** — ältere Einträge sind über die API nicht
erreichbar, auch nicht mit Werkzeugen.

**Fix:** `offset` überall ergänzen (gleiche Semantik wie die Logs), UI mit
„mehr laden".

### A6 — Keine Zeitraum-Filter (P2) — **behoben**

Weder die Logs noch das Änderungsprotokoll lassen sich auf einen Zeitraum
einschränken (`logs/queries` kennt `calling_aet`/`status`, `audit/config` nur
`entity`). Im Krankenhausbetrieb ist „zeig mir die Fehler von gestern"
(oder „von 08:00–12:00") die häufigste Frage — heute geht nur Blättern.

**Fix:** `from`/`to` (ISO-Zeit) auf `logs/queries`, `logs/stores`,
`audit/config`; UI-Felder dafür.

### A7 — Kein Einzelabruf (P3)

`GET /api/v1/<ressource>/{id}` fehlt für `sources`, `targets`, `rules`,
`transforms`, `station-rules`, `local-items`, `settings`. Die UI braucht es
nicht (sie hat die Liste), Integrationen und Skripte aber schon — heute muss
man die ganze Liste holen und filtern.

**Fix:** sieben `GET /{id}`-Routen (dünne Wrapper auf die bestehende
Abfragelogik) inkl. Vertragstests.

### A8 — Kein C-FIND-Test je Quelle (P3)

Der Betreiber kann per C-ECHO prüfen, ob eine Quelle **lebt** — aber nicht, ob
sie **Arbeitslisten liefert**. Genau das ist die häufigste Supportfrage
(„das Gerät sieht nichts"). Es gibt keinen Endpunkt, der eine echte
C-FIND-Abfrage gegen eine Quelle ausführt und die Antwort zeigt.

**Fix:** `POST /api/v1/sources/{id}/query` (optional mit Filterfeldern) →
Anzahl Antworten, Dauer, erste Treffer (PHI-frei: Accession/Station/Modalität/
Datum), Fehlertext. Ergebnis geht ins Query-Log.

### A9 — Keine Vorschau der **zusammengeführten** Arbeitsliste (P3)

`simulate/*` beantwortet „wohin würde dieser Fall gehen?" (Routing) und
„welche Quellen sieht diese Konsole?" (Stationsregeln) — aber nicht die
Kernfunktion: „was bekommt das Gerät **tatsächlich**?" (Fan-out + Merge +
Dedup + Transform + Cache). Das ist der einzige Weg, eine falsche Konfiguration
zu erkennen, **bevor** sie am Gerät auffällt.

**Fix:** `POST /api/v1/simulate/worklist` — führt die echte Aggregation aus
(dieselbe Codepfade wie der Live-Pfad) und liefert die zusammengeführten
Einträge mit Herkunft je Feld, Dedup-Entscheidungen, Cache-Nutzung und
Dauer je Quelle. PHI-frei konfigurierbar (Standard: wie im Query-Log).

### A10 — Kein Zertifikat-Upload (P3)

`POST /tls/self-signed` erzeugt Zertifikate; im Krankenhaus kommen sie aber von
der **PKI**. Heute muss man sie per Hand auf den Host kopieren und die Pfade in
den Einstellungen setzen — der Broker kann sie nicht annehmen.

**Fix:** `POST /api/v1/tls/upload` (Zertifikat/Schlüssel/CA als PEM), mit
Validierung (Schlüssel passt zum Zertifikat, Gültigkeit), Rechten `0600`,
Protokolleintrag, **niemals** Rückgabe des Schlüssels.

### A11 — Keine HL7-Nachricht im Detail (P3)

`GET /hl7/messages` listet nur (limit). Eine abgelehnte ORM-Nachricht kann man
weder im Detail ansehen noch erneut anwenden — der Betreiber muss sie neu
senden.

**Fix:** `GET /hl7/messages/{id}` (Roh-Nachricht + Parse-Ergebnis + Fehler) und
`POST /hl7/messages/{id}/reprocess` (dry-run-fähig, auditiert).

### A12 — Kleinere Lücken (P4)

- Kein Blick in die **zuletzt gesendeten ATNA-Nachrichten** (nur Zähler + ein
  Beispiel-XML).
- Kein **„Cache jetzt aktualisieren"** (nur löschen).
- Kein **Konfigurations-Diff zweier Exporte**.

### A13 — Veraltete Aussage in der Integrationsdoku (P2, Doku) — **behoben**

`docs/mwl-broker-integration.md` Zeile 118 behauptet:

> „Typed client is ready (`src/api/broker.ts`) — CRUD editors are a planned UI phase"

Die CRUD-Editoren **existieren** (`NodeFormDialog` + Quellen-/Ziel-/
Regel-/Transform-/Stationsseiten). Die Zeile muss weg.

### A14 — Bewusste Grenzen sind nicht als solche dokumentiert (P2, Doku) — **behoben**

Die Prüfung hat drei „fehlende" Fähigkeiten gefunden, die **Absicht** sind —
sie stehen aber nicht als Grenze in der Integrationsdoku, weshalb jede spätere
Prüfung sie erneut als Lücke meldet:

- **MPPS** (N-CREATE/N-SET): nicht Teil des Brokers — das RIS schließt Aufträge
  (in der Roadmap begründet, in der Integrationsdoku nicht).
- **Spool-Payload** ist absichtlich nicht über die API einsehbar (PHI).
- **Keine eigene API-Authentifizierung**: der Proxy authentifiziert.

**Fix:** Abschnitt „Bewusste Grenzen" in der Integrationsdoku.

## 3. Umgesetzt (Sprint 1+2)

| Befund | Umsetzung | Nachweis |
|---|---|---|
| **A1** | `rbac.is_read_only_request()` prüft die Absicht: Trockenläufe, C-ECHO und der TLS-Test bleiben für Nur-Leser erlaubt, `?dry_run=true` schaltet `hl7/orm` und `config/import` frei. `atna/test` und `notify/test` bleiben geschützt (sie senden echte Nachrichten) — die UI blendet genau diese zwei für Nur-Leser aus (`useCanWrite`) | 4 neue RBAC-Tests (u. a. „Trockenlauf 200, Anwenden 403"); live gegengeprüft |
| **A2** | `audit.record` in `DELETE /cache` und `/cache/sources/{id}` (Aktion `cache.clear` / `cache.clear_source`, mit Anzahl entfernter Einträge) | `test_clearing_the_cache_is_audited` |
| **A3** | `audit.record` + Logzeile in `reset-breaker` (vorheriger Breaker-Zustand, Akteur) | `test_breaker_reset_is_audited` (prüft den Akteur `mfa.schmidt`) |
| **A4** | `GET /status` liefert `version`, `started_at`, `uptime_s`; die Version kommt aus `pyproject.toml` (Install-Metadaten können veralten); die Übersicht zeigt eine Karte „Laufende Version / Laufzeit" | `test_status_reports_version_and_uptime`, UI-Test |
| **A5** | `offset` auf `spool`, `hl7/messages`, `cache/items` (wie bei den Logs); die Spool-Seite lädt seitenweise („Mehr laden") | `test_lists_can_page_deeper_with_offset`, UI-Test |
| **A6** | `since` (ISO-Datum/-Zeit) auf `logs/queries`, `logs/stores`, `audit/config`; Datumsfelder im Änderungsprotokoll und im Abfrageprotokoll; ungültige Werte → 422 mit Klartext | `test_logs_can_be_filtered_by_time`, UI-Test |
| **A13** | Die Zeile „CRUD editors are a planned UI phase" ist ersetzt (inkl. Transforms) | Doku |
| **A14** | Neuer Abschnitt „Deliberate boundaries" (MPPS, Spool-Payload/PHI, Proxy-Auth, PHI in Logs) und „Read/write split (RBAC)" in der Integrationsdoku | Doku |

**Zusätzlich gefunden und behoben:** Der Zeilenklick („Tabelleneintrag öffnet die
Bearbeitung") war nur bei Quellen und Zielen verdrahtet — Regeln, Transforms und
Stationsregeln hatten ihn nicht, und die Mobilkarten (die auf schmalen Geräten
die Tabelle ersetzen) ebenfalls nicht. Jetzt öffnet in **allen fünf** Listen ein
Klick (oder Enter/Leertaste) auf Zeile bzw. Karte die Bearbeitung, vorbelegt mit
dem Eintrag; Knöpfe/Schalter darin bleiben unberührt. Test in `RulesPage.test.tsx`.

**Entschieden für Sprint 3 (A9):** Die Vorschau der zusammengeführten
Arbeitsliste wird **PHI-frei ausgeliefert und über eine Einstellung
umschaltbar** (Standard: PHI-frei wie das Query-Log; das Umschalten ist im
Health-Panel sichtbar). Damit bleibt der Standard datenschutzfreundlich und die
Fehlersuche trotzdem möglich.

## 4. Empfohlene Reihenfolge (Sprint 3+4)

| Sprint | Inhalt | Aufwand |
|---|---|---|
| **1** | A1 (RBAC-Absicht) + A2 (Cache-Audit) + A3 (Breaker-Audit) — Sicherheit/Nachvollziehbarkeit | klein |
| **2** | A4 (Version/Uptime) + A5 (Offset) + A6 (Zeitraum) + A13/A14 (Doku) | klein–mittel |
| **3** | A8 (C-FIND-Test) + A9 (Merged-Vorschau) — die zwei stärksten Betreiber-Features | mittel |
| **4** | A7 (Einzelabruf) + A10 (Zertifikat-Upload) + A11 (HL7-Detail) + A12 | mittel |

Alle Punkte sind mit Tests, Doku und Commit abzuschließen; für A1 gehört ein
Test dazu, der die **Absicht** festschreibt (Trockenlauf bleibt für Nur-Leser
erlaubt, Anwenden nicht).
