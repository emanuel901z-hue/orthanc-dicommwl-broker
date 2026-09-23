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
- `POST /sources/{id}/reset-breaker` — Breaker einer Quelle sofort schließen
- `GET /health/config` — Konsistenz-Checks (Findings mit `code`/`severity`/`entity`)
- `GET /healthz/ready` — Readiness (DB + SCP; 503 wenn nicht bereit)
- `GET /audit/config` — Änderungsprotokoll (Before/After je Konfigurationsmutation)
- `GET /config/export`, `POST /config/import?dry_run=`, `POST /config/rollback/{audit_id}`
- `POST /simulate/route`, `POST /simulate/transform` — Dry-Run von Routing und Modify-Regeln
- `GET /cache/stats`, `GET /cache/items`, `DELETE /cache[/sources/{id}]` — Worklist-Cache
- `GET /spool`, `GET /spool/stats`, `POST /spool/{id}/retry`, `POST /spool/retry-all`,
  `DELETE /spool/{id}?reason=` — C-STORE-Spool (Store and Forward)
- `GET /notify/events`, `POST /notify/test` — Alerting (Webhook)
- `GET/POST /local-items`, `PUT/DELETE /local-items/{id}` — lokale Worklist-Items
- `POST /hl7/orm?dry_run=`, `GET /hl7/messages` — HL7-ORM-Schnittstelle (MLLP-Listener optional)
- `GET/POST /station-rules`, `PUT/DELETE /station-rules/{id}` — Per-Station-Regeln
- `POST /simulate/station` — Vorschau: welche Quellen sieht eine Konsole?
- `GET /atna/stats`, `POST /atna/test`, `GET /atna/sample` — ATNA-Audit-Trail
- `GET /tls/overview`, `POST /tls/self-signed`, `POST /tls/test` — DICOM-TLS und Zertifikatsverwaltung
- `GET /rbac/status` — Zugriffsmodus für den Aufrufer (Lesen vs. Schreiben)
- `GET /retention`, `POST /retention/purge?table=` — Aufbewahrung und manuelles Aufräumen
- `GET /logs/queries`, `GET /logs/stores` (paged, Filter: aet, source, status, since)
- `GET /status` — SCP-Listener, Echo-Matrix (Quellen+Ziele inkl. `breaker_state`), Zähler
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

### Circuit Breaker + Konsistenz-Checks

`source_breaker` hält je Quelle Zustand (`closed|half_open|open`), Fehlerzähler
und Sperrzeit — persistiert, damit ein Neustart eine tote Quelle nicht
vergisst. Der C-FIND-Fan-out überspringt offene Quellen
(`per_source = "breaker_open"`) statt pro Abfrage den vollen Timeout zu zahlen;
nach `breaker_open_seconds` erfolgt ein Testversuch (half-open). Schwellen sind
Settings (`breaker_fail_threshold`, `breaker_open_seconds`).

`health_checks.py` prüft die Konfiguration auf die typischen
Produktionsfehler (kein Default-Ziel, Regeln auf deaktivierten Knoten, tote
Quellen, offene Breaker, leere AET-Allowlist, AET-Kollision mit dem Broker
selbst) und liefert Findings mit stabilem `code` — die UI übersetzt sie und
verlinkt direkt ins betroffene Formular.

### MFA-Testumgebung (unbedarfter Anwender)

`./mfa-test.sh` fährt den isolierten Test-Stack hoch und spielt die Journey
einer MFA durch: Unsinn eintippen, zu früh speichern, korrigieren, Zurück/F5,
gefährliche Regeln anlegen. Der Bericht
(`orthanc-explorer-3-usable/e2e/stack/screenshots/mfa-journey-*.md`) listet jede
Prüfung mit „OK"/„LÜCKE". Dazu gehören die „Was ist das?"-Hilfe je Seite
(drei Abschnitte: worum geht es, was trage ich ein, was geht schief) und
Formular-Entwürfe in `sessionStorage` mit einer Stunde Gültigkeit.
Gefundene und behobene Lücken:
Formulare überleben jetzt Zurück/F5 (Entwurf in `sessionStorage` + Warnung beim
Verlassen), `GET /sources` lieferte 500 (Eingabe-Prüfung lief auf
Antwort-Modellen), Erfolgsmeldungen gibt es für **alle** Schreibaktionen,
Feldmeldungen sind live und als `role="alert"` ausgezeichnet, und der Server
lehnt unsinnige Adressen/AETs ab. Details:
[docs/mfa-usability-test.md](docs/mfa-usability-test.md).

### i18n (react-i18next, 9 Sprachen)

Der Broker nutzt **ausschließlich** react-i18next (`useTranslation()` in
Komponenten und Hooks) — kein eigenes `t()`; ein Guard-Test
(`src/features/broker/i18n-usage.test.ts`) erzwingt das und prüft zusätzlich,
dass jeder referenzierte Schlüssel in der Referenzdatei existiert. Der sichtbare
Rahmen (Titel, Tabellenköpfe, Knöpfe, Dialoge, Hilfe-Überschriften) ist in alle
neun OE3-Sprachen übersetzt; ausführliche Texte liegen auf Deutsch und Englisch
vor und fallen schlüsselweise auf Englisch zurück. Debuggen über `?lng=fr`,
`?i18nDebug=1`, `window.__i18n`; `npm run i18n:check` prüft die Abdeckung in CI.

### UI-Härtung (DAU-Sicherheit)

Die [DAU-Gap-Analyse](docs/ui-dau-gap-analysis.md) prüft die Oberfläche auf
Fehleingaben und stilles Scheitern. Sprint 9 hat die P1-Befunde behoben:
**jede** Einstellung meldet Erfolg (Toast) und Ablehnung (Toast + Inline-Fehler
mit Server-Text); Integer-Felder sind `type="number"` mit `min`/`max` und
Klartext-Bereich (die API liefert die Grenzen), Enums sind Auswahlfelder;
Stationsregeln warnen, wenn sie alle Quellen verbirgen (plus Health-Finding
`station_rule_hides_all`); Dialoge sind auf 375 px vollständig bedienbar.

### Eingabeführung (Sprint 10 der DAU-Analyse)

`lib/setting-rules.ts` spiegelt die Server-Validierung (bool/int-Bereich/enum/
url/path/aets) und wird von der Settings-Seite und den Karten genutzt — ungültige
Werte werden **vor** dem Senden gemeldet und der Speichern-Knopf gesperrt. Die
lokale Worklist hat Datum-/Zeit-Picker, Auswahlen und Musterprüfungen statt
Freitext; Karten speichern **einmal pro Änderung** (Entwurf + Speichern beim
Verlassen) statt bei jedem Tastendruck.

### Zugriffssteuerung (RBAC) und Retention

**RBAC:** Der Proxy authentifiziert und übergibt die Rollen im Header
(`rbac_roles_header`, Default `X-OE3-Roles`). `rbac_mode=enforce` schaltet die
Trennung scharf: jeder Nicht-GET-Request braucht die Rolle `rbac_write_role`
(Default `brokerWrite`), sonst 403 mit verständlicher Meldung. Lesen bleibt
offen. `GET /rbac/status` liefert der UI `can_write` — sie zeigt Lesern einen
Banner und deaktiviert die Schreibaktionen. Default: aus.

**Retention:** pro Tabelle konfigurierbar (`retention_*_days`, 0 = für immer):
Query-Log 90, Store-Log 90, HL7 30, Spool 7, lokale Einträge nur über ihre
eigene Gültigkeit, Änderungsprotokoll 0 (Rechnungslegung). `GET /retention`
zeigt Zeilen/ältesten Eintrag/Fenster, `POST /retention/purge` räumt auf
(auditiert) — nichts wird implizit gelöscht.

### DICOM-TLS (mTLS) und Zertifikatsverwaltung

Zwei Richtungen, getrennt schaltbar, **standardmäßig aus**: eingehend über einen
**zweiten Listener** (`tls_inbound_port`, Default 2762) neben dem Klartext-Port —
das erlaubt die stufenweise Umstellung einer Modalität nach der anderen — und
ausgehend je Quelle/Ziel (`tls`, `tls_verify`) mit globalen Trust-/Identitäts-
dateien. `tls_inbound_client_auth` schaltet mTLS (`none|optional|required`).

Für Betreiber ohne PKI: `POST /tls/self-signed` erzeugt ein Zertifikat (SANs,
optional als CA), der private Schlüssel wird mit 0600 geschrieben und nie über
die API ausgegeben. `GET /tls/overview` zeigt Zustand und Ablauf jedes
konfigurierten Zertifikats, `POST /tls/test` macht einen **echten Handshake** mit
Protokoll, Cipher und Peer-Zertifikat und optional einem C-ECHO über TLS.
Ablauf und Fehlkonfigurationen erscheinen als Health-Findings und lösen das
Alerting-Ereignis `tls_certificate_expiring` aus.

### Lokale Worklist-Items und HL7-ORM

Notfälle und ungeplante Untersuchungen führt der Broker selbst
(`local_worklist_item`): sie werden mit der **höchsten Priorität** in jede
passende C-FIND-Antwort gemischt (Matching auf Patient/Zugang/Modalität/Station/
Datum) und laufen unter der Pseudo-Quelle `local`, die nie abgefragt wird, aber
in Routing-Regeln nutzbar ist.

HL7-ORM-Aufträge kommen über `POST /hl7/orm` (mit Trockenlauf) oder den
**MLLP-Listener** (`hl7_mllp_enabled`); derselbe Parser und Upsert-Pfad für
beide. `NW` legt an, `XO`/`SC` ändert, `CA`/`OC` storniert; unmappbare Felder
erscheinen als Warnung statt als halber Eintrag. Der Audit-Snapshot lokaler
Einträge enthält bewusst **keine Patientendaten** (sonst läge PHI im
Konfigurations-Export).

### Per-Station-Filter und -Priorität

`station_rule` verbirgt Quellen vor einer Konsole (`deny`) oder zeigt nur
bestimmte (`allow`) und kann die Merge-Reihenfolge für diese Station umdrehen
(`source_priority`). Gefiltert wird **nach dem Merge** — die Deduplizierung
bleibt für jede Station identisch. `POST /simulate/station` zeigt vorab, was eine
Konsole sieht.

### ATNA-Audit-Trail (IHE, Syslog/TLS)

`atna.py` erzeugt PS3.15-Audit-Nachrichten (`Query`, `Import`, `Export`,
`Security Alert`) als RFC-5424-Syslog über TCP oder TLS an die eigene
Audit-Record-Repository. Eine begrenzte Queue mit Worker-Thread sorgt dafür, dass
ein nicht erreichbares ARR den DICOM-Verkehr nie blockiert (verworfene Nachrichten
werden gezählt). Bewusst **opt-in** (`atna_enabled`).

### Alerting (Webhook)

`notify.py` schickt Broker-Ereignisse als JSON-POST an einen Webhook
(Slack/Teams-kompatibel: `text` plus strukturierte Felder). Neun Ereignisse sind
im Katalog (`GET /notify/events`): Quelle/Ziel up/down, Breaker offen,
Spool-Dead-Letter/-Rückstand/-voll, Konfigurationsfehler.

Die Zustellung läuft **immer** auf einem Hintergrund-Thread — ein langsamer oder
toter Webhook darf nie einen C-FIND/C-STORE verzögern; Fehler werden geloggt und
gezählt. Gemeldet wird nur der **Übergang** (nicht jeder Check), und gleiche
Ereignisse für dasselbe Objekt werden `notify_min_interval_s` lang gedämpft.
Die Webhook-URL wird nie vollständig geloggt (sie trägt ein Secret-Token).

### C-STORE-Spool (Store and Forward)

Kann eine Instanz nicht zugestellt werden, wird sie **nicht verworfen**: der
Payload wird atomar auf Platte geschrieben (`spool_dir`, eigenes Volume), die
Metadaten landen in `store_spool`, und ein Worker wiederholt mit exponentiellem
Backoff bis `spool_max_attempts` (danach Dead Letter). Nach erfolgreicher
Zustellung wird die Datei gelöscht; die Zeile bleibt `spool_retention_s` als
**Duplikatsschutz** — `spool.is_duplicate` greift deshalb auch im Live-Pfad, damit
ein wiederholter C-STORE nicht doppelt ins PACS geht.

Budget: `spool_max_items` (20000) und `spool_max_bytes` (10 GiB). Ist es
erschöpft, **weist der Broker ab** (Modalität bekommt einen Fehler, Health-Finding
`spool_full`) statt still zu verwerfen. `accept_when_queued` (Default an) meldet
der Modalität Erfolg, sobald die Instanz sicher liegt.

### Schema-Migrationen (Alembic)

Das Basisschema kommt aus den Modellen (`Base.metadata.create_all()`).
Geordnete Migrationen für **bestehende** Installationen liegen in `migrations/`:
`0001_baseline` wird nur gestempelt, `0002_cache_columns` und `0003_store_spool`
sind die ersten echten Revisionen und **defensiv** (Existenzprüfung), weil eine
frische Datenbank das aktuelle Schema schon hat. `init_db()` führt beides aus:
`create_all()` (fehlende Tabellen) + `alembic upgrade head`.

### Worklist-Cache mit Stale-Fallback

Der Upstream ist die Wahrheit: eine erfolgreiche Antwort **ersetzt** den
Snapshot der Quelle vollständig, abgeschlossene Aufträge verschwinden also
sofort (Medavis-Semantik; dcm4chee steuert dasselbe über HL7 ORM/MPPS und
blendet `COMPLETED` per `dcmHideSPSWithStatusFromMWL` aus). Der Cache greift
**nur** bei Fehlern oder offenem Breaker, höchstens `cache_stale_max_s`
(Default 120 s), filtert erledigte Schritte (`(0040,0020)`) und wird über
`cache_max_items` begrenzt. Erledigte Queries werden im Query-Log als
`served_stale` geführt und der Gesamtstatus wird `partial`.

Der Payload enthält PHI (das ist der Zweck einer Worklist) → nur interne DB,
keine Logs, API liefert nur Metadaten, automatischer Purge und ein expliziter
„Cache leeren"-Knopf. Details und die Recherche-Grundlage:
[docs/roadmap-worklist-broker.md](docs/roadmap-worklist-broker.md).

### Simulation (Dry-Run) — Routing und Modify-Regeln

`simulate.py` beantwortet „wohin geht dieser Fall und wie sehen die Kopfdaten
danach aus“ **ohne** Versand. Entscheidend: die Zielauflösung liegt in
`routing.py` und wird vom C-STORE-Pfad (`dimse`) **und** der Simulation
aufgerufen — ein Dry-Run kann also nicht von der Realität abweichen (per Test
`test_simulation_matches_the_live_resolver` abgesichert). Modify-Regeln laufen
über dieselben `transforms.applicable`/`apply_transforms`.

### Änderungsprotokoll, Export/Import, Rollback

`config_audit` protokolliert jede Konfigurationsmutation mit serialisiertem
Before/After (zentral in der API-Schicht). Darauf setzen drei Funktionen auf:
Diff-Ansicht, Rollback (`before` wiederherstellen; Create → löschen,
Delete → neu anlegen) und der portable Export (`schema_version`, Referenzen
**per Name**). Der Import ist Upsert-only mit Dry-Run-Diff — er löscht nie
implizit, weil ein fehlender Eintrag in einer Datei keine Aussage über die
Produktion ist.

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
| `pytest` | 398 Tests grün (inkl. DIMSE-Integration in-process) |
| OpenAPI | 66 Operationen vollständig dokumentiert (Summary, Beschreibung, Parameter, Antworten, Fehler) — Vertrag per Test erzwungen |
| `npm run test` / `tsc` / `lint` | 490 Tests, 0 Errors |
| `npm run i18n:check` | Rahmen in allen 9 Sprachen, Referenzsprachen synchron |
| Playwright Stack-E2E (Desktop 1280x800 + Mobile 375x812) | 55/55 grün, 0 Console-/Page-/Netzwerk-Fehler |

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
backend pytest (392) → frontend tsc → lint → vitest (441) → docker-e2e
(48 Browser-Tests + DIMSE-Smokes + Breaker-/Cache-/Spool-/Webhook-/HL7-/ATNA-/TLS-/RBAC-Szenario). Verifiziert: alle Stages grün.
`--quick` überspringt die Docker-Stage.

#### Coverage-Audit (2026-09)

Gemessen mit `pytest-cov` bzw. `vitest --coverage`:

| Bereich | Statements | Anmerkung |
|---|---|---|
| Backend `mwl_broker/` | **95 %** | gemessen 23.09.2026 mit `pytest --cov` (626 Tests): station_rules/routing/transforms/orders/rbac/metrics/models/settings_service 100 %, upstream 99 %, schemas 99 %, merges 96 %, retention 96 %, tls 91 %, hl7 95 %, local_worklist 95 %, notify 93 %, spool 94 %, stats 94 %, mpps 89 %, main 88 % |
| Frontend Broker-UI | **89–98 %** je Ordner | gemessen 23.09.2026 mit `vitest --coverage` (606 Tests): `features/broker/lib` 98,2 %, `hooks` 96,9 %, `pages` 94,7 %, `api/broker.ts` 88,6 % (die restlichen SPA-Bereiche sind bewusst nicht Teil dieses Slices) |

Ergänzte Tests für zuvor ungedeckte Pfade: Rules-Update/Delete, Target-Echo,
Log-Filter + Pagination-Validierung, `/metrics`, Lifespan (Seed + SCP-Bind),
Settings-Update/Reset + Validierungsrandfälle, `seen_items`-Retention-Purge,
Echo-Loop (inkl. Purge-Trigger und DB-Fehlerresistenz), Mock-RIS-Query-Filter,
Transform-Validierungsmeldungen, C-ECHO-Fehlerstatus.
Restliche Lücken sind bewusst: `mock_ris.main()` (argparse/Server-Start des
Demo-Tools, live im Stack verifiziert) und defensive `except`-Zweige der
DB-Schreibpfade (Fault-Injection ohne Erkenntnisgewinn).

#### OpenAPI/Swagger-Vollständigkeit

Audit gegen `/openapi.json` (26 Operationen, 15 Schemas): jede Operation hat
Summary + Tag + Response-Description (kein FastAPI-Default „Successful
Response" mehr), **alle** Path- und Query-Parameter sind beschrieben,
Request-Bodies dokumentiert, jedes Schema-Feld hat eine Beschreibung
(ausgenommen die FastAPI-internen `HTTPValidationError`/`ValidationError`).
`test_openapi_documents_all_endpoints` erzwingt diesen Vertrag.

#### Browser-Verifikation (Deep-Audit)

`e2e/stack/verify-ui.cjs` (Chromium headless, Desktop 1400×900 + Mobile
375×812): 6 Broker-Seiten × (H1-Anzahl, Overflow, Alt-Texte) + echte
CRUD-Flows (Quellen/Ziele/Regeln/Modify-Regeln/Settings) jeweils gegen die
REST-API gegengeprüft, C-ECHO-Button, Query-Log, mobile Sidebar-Navigation —
**56/56 Checks grün**, 0 unerwartete Console-/Netzwerk-Fehler.

Gefundene und behobene Defekte:

- **Mobile Broker-Tabellen abgeschnitten**: Bei 375 px wurden die Action-Buttons
  rechts aus dem Card-Bereich geschoben (Store targets: „Actions" halb sichtbar).
  Fix: die vier Konfig-Tabellen rendern unterhalb `md` jetzt als Cards
  (`ConfigRowCard`, Fork-Konvention „Mobile Card Views"), Label/Wert gestapelt
  damit DICOM-Endpunkte nicht mitten im Token umbrechen.
- **`ConfigRowCard` rendete die Badges nicht** (destrukturiert, aber nicht
  ausgegeben) → „default"/„disabled" fehlten auf Mobile. Von der e2e-Suite
  gefunden.
- **Modify-Regeln auf Mobile ohne Operations-Anzeige** → Operations jetzt als
  Card-Feld. Ebenfalls von der e2e-Suite gefunden.
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
| 8 | Sprint 1 der Roadmap: Circuit Breaker + Health-Panel + `/healthz/ready` | ✅ |
| 9 | Sprint 2 der Roadmap: Simulation + Config-Audit/Export/Rollback | ✅ |
| 10 | Sprint 3 der Roadmap: Worklist-Cache mit Stale-Fallback | ✅ |
| 11 | Sprint 4 der Roadmap: C-STORE-Spool + Alembic-Migrationspfad | ✅ |
| 12 | Sprint 5 der Roadmap: Alerting/Webhooks | ✅ |
| 13 | Sprint 6 der Roadmap: lokale Worklist + HL7-ORM, Stationsregeln, ATNA | ✅ |
| 14 | Sprint 7 der Roadmap: DICOM-TLS/mTLS + Zertifikatsverwaltung | ✅ |
| 15 | Sprint 8: RBAC-Trennung, Retention/Löschkonzepte, flexibles Alerting | ✅ |
| 16 | Sprint 9: UI-Härtung P1 (Rückmeldung, typisierte Eingaben, Dialoge) | ✅ |
| 17 | Sprint 10: Eingabeführung (Picker, Vorprüfung, ein Write pro Änderung) | ✅ |
| 18 | Sprint 11: Bedienfluss (Dirty-Guard, Duplikate, A11y) — DAU-Analyse abgeschlossen | ✅ |
| 19 | MFA-Testumgebung (unbedarfter Anwender) + behobene Befunde | ✅ |
| 20 | Seiten-Hilfe, Entwürfe für alle Formulare, Entwurfs-Ablauf (1 h) | ✅ |
| 21 | i18n aufgeräumt (react-i18next, 9 Sprachen, Debug, Abdeckungsprüfer) | ✅ |
| 22 | API-Vollständigkeit: RBAC-Absicht, Cache-/Breaker-Audit, Version/Uptime, Paging, Zeitraumfilter, Einzelabrufe, PKI-Upload, HL7-Replay, Cache-Refresh, C-FIND-Test, Merged-Vorschau | ✅ |
| 23 | **MPPS** (N-CREATE/N-SET) + Status-Rückmeldung als HL7 an das RIS | ✅ |
| 24 | **Feldweiser Merge** + konfigurierbares **HL7→DICOM-Mapping** | ✅ |
| 25 | **DICOM Conformance Statement** + IHE-Aussage (durch Tests an den Code gebunden) | ✅ |
| 26 | **Statistik/Reporting** (Auslastung, Fehler, Tagesreihe) + Migration-Guard | ✅ |
| 27 | **UPS-RS** (DICOMweb-Worklist: Suche/Abruf/Anlegen/Statuswechsel) als Subset | ✅ |

Die nächsten Ausbaustufen stehen in
[docs/next-steps.md](docs/next-steps.md) (Funktion, Betrieb, Nachweise,
Beschaffung) und in
[docs/roadmap-worklist-broker.md](docs/roadmap-worklist-broker.md) mit
Backend-/API-Entwurf, DAU-sicherem OE3-Frontend und Teststrategie je Funktion.
Empfehlung nach dem Stand vom 22.09.2026: zuerst **Lasttest** (Dimensionierung
und Validierungslücke), dann **Interop-Nachweis mit Fremdsystemen**, dann
**Hochverfügbarkeit** — letztere erst nach einem Design-Vorlauf, weil der Spool
noch kein Claiming hat (siehe `next-steps.md` §3).

## Offene Punkte / Risiken

- **Charset** je Quelle testen (deutsche Namen, `ISO_IR 100` vs `ISO_IR 192`).
- **Dedupe-Strategie** muss fachlich bestätigt werden (gleicher Patient in
  zwei RIS? Accession-Kollisionen?).
- `seen_items` als Routing-Basis funktioniert nur, wenn die Worklist vorher
  abgefragt wurde — Fallback-Regel zwingend konfigurierbar.
- Orthanc kann parallel weiterhin Bilder direkt annehmen (Port 4242); der
  Broker-Port 11113 ist der empfohlene Eingang für Modalitäten.
