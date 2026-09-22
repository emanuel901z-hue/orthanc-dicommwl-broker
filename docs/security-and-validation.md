# Sicherheit, Härtung und Validierung

Stand: 22.09.2026 · Für Betreiber, Datenschutzbeauftragte und Ausschreibungen.

Dieses Dokument beschreibt, **was der Broker technisch tut**, **was die
Test-Suiten beweisen** und **was nicht geprüft wurde**. Es ist bewusst kein
Konformitäts- oder Zertifizierungsdokument: eine CE-Kennzeichnung als
Medizinprodukt ist nicht beabsichtigt (siehe
[`next-steps.md`](next-steps.md)), und es hat **keine unabhängige
Sicherheitsprüfung** stattgefunden.

## 1. Schutzbedarf und Datenfluss

Der Broker verarbeitet Patientendaten (Arbeitslisten, Bild-Metadaten,
Statusmeldungen) und ist damit ein System mit hohem Schutzbedarf nach § 22
BDSG/Art. 32 DSGVO. Er ist **nicht** das führende System: die Patientendaten
kommen aus RIS/KIS, die Bilder gehören ins PACS.

| Datum | Wo | Aufbewahrung |
|---|---|---|
| Arbeitslisten-Antworten | im Speicher, Cache-Snapshots (JSON) | Cache: Minuten (`cache_stale_max_s`) |
| Abfrage-/Store-Protokoll | Datenbank, **PHI-frei** (Zugangsnummer, Station, Modalität, Status) | `retention_query_log_days` / `_store_log_days` |
| Routing-Herkunft (`seen_items`) | Datenbank, mit **PatientID** | `retention_local_items_days` |
| Lokale Einträge, Patienten-Zusammenführungen | Datenbank, mit Patientendaten | wie oben |
| MPPS-Schritte | Datenbank, Identifier + Zeiten | `retention_mpps_days` |
| HL7-Rohnachrichten | **nur** wenn `hl7_store_raw=true` | `retention_hl7_days` |
| Spool (Bilder) | Plattenvolume, unverschlüsselt | bis zur Zustellung |
| Änderungsprotokoll | Datenbank, **ohne** Patientendaten | Standard: für immer |

**Grundsatz im Code:** `PatientName` erscheint **nie** in Logs, Metriken oder
Änderungsprotokoll. `PatientID` nur dort, wo sie zum Zuordnen nötig ist.
`tests/test_stats.py::test_overview_is_phi_free` und die Audit-Tests erzwingen
das.

## 2. Härtung: was eingebaut ist

| Bereich | Maßnahme | Prüfbar |
|---|---|---|
| **Transport (eingehend)** | DICOM-TLS-Listener optional (`tls_inbound_enabled`), mTLS bis `tls_inbound_client_auth=required`; Klartext-Port bleibt getrennt | TLS-Karte, `POST /tls/test` |
| **Transport (ausgehend)** | je Knoten `tls` + `tls_verify`; Abschalten der Prüfung erscheint als Health-Warnung | Health-Findings |
| **Zertifikate** | Einspielen aus der PKI (`POST /tls/upload`) mit Prüfung (Schlüssel gehört zum Zertifikat, Gültigkeit); private Schlüssel **nie** über die API, Dateien mit 0600 | `test_tls*` |
| **Zugriffskontrolle** | `rbac_mode=enforce`: jeder Schreibzugriff braucht die Rolle aus `X-OE3-Roles`; **Leseabsicht** (Trockenläufe, C-ECHO, C-FIND-Test) bleibt erlaubt | `test_rbac.py` |
| **AET-Filter** | `allowed_calling_aets`; leer = jeder darf (Health-Hinweis, `setup.sh` fragt danach) | Health-Findings |
| **Web-API** | Request-Größenlimit 2 MiB (`BROKER_MAX_BODY_BYTES`), Fehler mit Request-ID statt Stacktrace, Zeitlimits an allen Upstream-Aufrufen | `test_api.py` |
| **Proxy/UI** | Sicherheits-Header im nginx (`nosniff`, `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy`, `Permissions-Policy`), API/Orthanc binden standardmäßig an `127.0.0.1` | `deploy/oe3-stack.nginx.conf` |
| **Ausfallsicherheit** | Circuit Breaker, Cache-Brücke, Spool mit **Abweisung statt Verwerfen**, Timeouts, DB-Pool dimensioniert | `test_dimse_integration.py`, `test_spool.py` |
| **Nachvollziehbarkeit** | jede Konfigurationsänderung mit Vorher/Nachher und Akteur, Rollback je Eintrag; ATNA-Export optional | `test_audit.py`, `test_atna*` |
| **Betrieb** | geführter Bootstrap (`./setup.sh`) warnt vor schwachen Zugangsdaten, offenen Bindungen und leerer AET-Liste; Sicherung mit geprüftem Round-Trip | `setup.sh --check`, `deploy/backup-roundtrip-test.sh` |
| **Lieferkette** | `pip-audit` + `audit-ci` in der CI; Push nur über `./pre-push-fork.sh` (Blacklist + Secret-Scan); Zugangsdaten liegen außerhalb des Repos | `ci-local.sh` |

## 3. Bekannte Grenzen (bewusst, nicht übersehen)

1. **Ein Datenbankbenutzer.** Broker und Orthanc nutzen denselben
   Postgres-Benutzer. Für gehärtete Installationen: eigene Rolle für die
   Datenbank `mwl` anlegen (`CREATE ROLE mwl LOGIN PASSWORD …; GRANT ALL ON
   DATABASE mwl TO mwl;`) und `BROKER_DATABASE_URL` in `.env` darauf umstellen —
   der Broker braucht keinen Zugriff auf `orthanc`.
2. **Spool ist nicht verschlüsselt.** Wer Zugriff auf das Volume hat, hat
   Zugriff auf die gepufferten Bilder. Abhilfe: verschlüsseltes Volume
   (LUKS) oder das Ziel so auslegen, dass der Spool klein bleibt.
3. **Kein Zertifikat-zu-AET-Mapping** (ATNA „Node Authentication" im engeren
   Sinn): TLS prüft die Kette, nicht ob dieses Zertifikat zu dieser AET gehört.
4. **Keine Benutzerverwaltung im Broker.** Rollen kommen vom vorgelagerten
   Proxy; der Broker glaubt dem Header. Wer den Proxy umgehen kann, umgeht RBAC
   — deshalb bindet die API standardmäßig nur auf `127.0.0.1`.
5. **Kein Rate-Limiting** je Quelle/Station (nur Zeitlimits und
   Assoziationsgrenze). Bei Missbrauch ist die Angriffsfläche der vorgelagerte
   Proxy.
6. **Keine Verschlüsselung „at rest"** in der Datenbank (Postgres-Standard).
   Für strengere Anforderungen: verschlüsselte Platte oder
   Postgres-Verschlüsselung.

## 4. Was die Tests beweisen — und wie man sie als Validierung nutzt

Die Suiten sind die Grundlage einer Abnahme: sie sind reproduzierbar, in der CI
verdrahtet und prüfen Verhalten, nicht Implementierung.

| Ebene | Umfang | Was sie belegt |
|---|---|---|
| `pytest` (Backend) | 605 Tests | DIMSE-Verhalten über echte Assoziationen (C-FIND, C-STORE, C-ECHO, MPPS N-CREATE/N-SET/**N-GET**), MLLP über echte Sockets, TLS/mTLS, RBAC, Aufbewahrung, Aggregation/Merge, Patienten-Zusammenführung, Reporting, UPS-RS, Auftragskontext (MADO-Korrelation), ADT-Ereignisse (A08/A24/A40/A47) und Aufträge (ORM^O01/OMG^O19) über REST und MLLP, Ablehnung von Nicht-Aufträgen (ORU^R01), Nebenläufigkeit (Breaker/Cache unter parallelen Abfragen), Hochverfügbarkeit (Spool-Claim, Instanz-Heartbeat), die Betriebsdokumente (Alarmnamen, Runbook-Anker, Skripte, Hilfeseiten), Interoperabilität gegen Fremdsoftware (mehrwertige Attribute, Cache-Fehler), Schema-Migrationen |
| `vitest` (Frontend) | 594 Tests | jede Broker-Seite und -Karte, Fehlerpfade, Berechtigungslogik, IID-Einstiegspunkt (RAD-106) |
| `verify-ui.cjs` | 149 Checks | jede Seite in Desktop und Mobil: keine Konsolen-/Netzwerkfehler, genau ein `<h1>`, kein Overflow, erwartete Inhalte |
| `verify-screens.cjs` | 225 Checks + 52 Bilder | jede Ansicht und jeder Dialog, inkl. Rohschlüssel-Erkennung |
| Playwright | 55 Tests | echte Bedienabläufe gegen den laufenden Stack (Konfiguration, MFA-Reise, Audit/Rollback, Spool) |
| `backup-roundtrip-test.sh` | 1 Ablauf | Sicherung → Daten zerstören → Wiederherstellung → Daten wieder da |
| `deploy/interop-test.sh` | 15 Prüfungen | Interoperabilität gegen **Fremdsoftware**: DCMTK (fremdes RIS, fremde Modalität, fremdes PACS) und dcm4che (fremder MPPS-SCU, fremder HL7-Sender/-Empfänger) — fand **sieben** Fehler, die eigene Tests nicht sehen konnten ([`interop.md`](interop.md)) |
| `deploy/ha-smoke.sh` | 9 Prüfungen | zwei Instanzen auf gemeinsamer DB/Volume: jedes Bild genau **einmal** zugestellt ([`ha.md`](ha.md)) |
| `ci-local.sh` | alle Stages | dass nichts davon kaputt ist, bevor gepusht wird |

**Ablauf für eine Abnahme** (Vorschlag, ohne Zertifizierungsanspruch):

1. Zielumgebung nach [`production-setup.md`](production-setup.md) aufsetzen,
   `./setup.sh --check` dokumentieren (Health-Findings = Ausgangszustand).
2. `./ci-local.sh` auf dem Zielhost laufen lassen und das Ergebnis abzeichnen.
3. `./test-stack.sh` (ephemerer Stack) — belegt DIMSE-Smokes, Oberfläche und
   Sicherungs-Round-Trip, ohne die Produktivdaten zu berühren.
4. Die drei Betriebsfälle aus dem [Runbook](runbook.md) durchspielen: Quelle
   abschalten (Cache greift, Alarm kommt), Ziel abschalten (Spool, Dead Letter,
   erneut senden), MPPS-Rückmeldung blockieren (Zähler, erneut senden).
5. Ergebnis mit Datum, Version (`/api/v1/status`) und den Health-Findings
   ablegen.

## 5. Patch- und Änderungsprozess

1. **Sicherung zuerst**: `./deploy/backup.sh` (inkl. `.env`).
2. `git pull --recurse-submodules`, dann `./build.sh --health`.
   Der Broker **verweigert den Start**, wenn die Migrationen nicht zur
   Datenbank passen (statt 500er zu liefern).
3. `./setup.sh --check` — neue Health-Findings ansehen.
4. Bei Sicherheitsupdates der Abhängigkeiten: `pip-audit`/`npm audit` in der CI
   beachten; Images mit `./build.sh --no-cache` neu bauen.
5. Zertifikate: Restlaufzeit steht als Metrik (`mwl_tls_certificate_days_left`)
   und als Alarmregel bereit.
6. Notfall (Verdacht auf Kompromittierung): **nichts löschen**, Logs und
   Sicherung sichern, Broker stoppen (`./build.sh --down`, **ohne** `--volumes`),
   Zugangsdaten rotieren (Dateien unter `~/.config/git/credentials-*`, Postgres-,
   Broker- und Proxy-Zugangsdaten), dann melden.

## 6. Offen für einen echten Sicherheitsnachweis

Nicht durchgeführt und für eine belastbare Aussage nötig:

- **Penetrationstest** der API und des DICOM-Listeners durch Dritte.
- **Bedrohungsmodell nach IEC 81001-5-1** mit dokumentierter Risikobewertung.
- **Lasttest** — inzwischen durchgeführt ([`loadtest.md`](loadtest.md): Harness,
  Messwerte, gefundene Nebenläufigkeitsfehler, benannte Lücken). Was weiter
  fehlt, ist die Wiederholung **auf der Zielhardware** und unter Dauerlast: die
  vorliegenden Zahlen stammen von einem Entwicklungsrechner mit parallel
  laufendem Stack.
- **Datenschutz-Folgenabschätzung** durch den Betreiber (der Broker ist
  Verarbeitung im Auftrag, nicht Verantwortlicher).

## 7. Bekannte Grenzen der Hochverfügbarkeit

Seit B1 dürfen zwei Broker-Instanzen dieselbe Datenbank und dasselbe
Spool-Volume teilen ([`ha.md`](ha.md)). Was das **nicht** leistet:

- **At-least-once, nicht exactly-once:** stirbt eine Instanz zwischen dem
  erfolgreichen Senden und dem Zurückschreiben, wird der Eintrag nach Ablauf der
  Lease erneut zugestellt — das PACS kann dasselbe Bild zweimal bekommen. Ein
  Duplikat ist heilbar, ein verlorenes Bild nicht; der Kompromiss ist bewusst.
- **Kein Fencing:** eine eingefrorene, aber lebende Instanz gibt ihre Lease erst
  nach Ablauf frei.
- **Datenbank und Spool-Volume bleiben Single Points of Failure.** Die
  Verfügbarkeit des Brokers ist nicht die Verfügbarkeit seiner Datenhaltung.
- **Der Endpunkt wird nicht verschoben:** die Modalitäten erreichen die aktive
  Instanz über VIP oder Load Balancer — das ist Netzwerk-/Deployment-Aufgabe.
