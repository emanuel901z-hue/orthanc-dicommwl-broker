# Support und SLA — Konzept und Vorlage

Stand: 22.09.2026 · Ergebnis von **C4** aus [`next-steps.md`](next-steps.md)

> **Das ist eine Vorlage, kein Vertrag.** Reaktionszeiten, Rufbereitschaft und
> Eskalationswege kann nur der Betreiber zusagen — der Broker ist Software, keine
> Serviceorganisation. Was hier **fest** steht, ist die technische Seite: welche
> Alarme es gibt, was der Broker zur Diagnose beiträgt und wo die Grenzen
> verlaufen. Die mit `⟨…⟩` markierten Felder füllt der Betreiber aus.

## 1. Rollen — wer macht was

| Rolle | Wer | Aufgabe | Nicht seine Aufgabe |
|---|---|---|---|
| **1st Level** | Klinik-IT / Servicedesk | Alarm annehmen, die drei Werkzeuge aus [`runbook.md`](runbook.md) §0 nutzen, bekannte Fälle nach Runbook abarbeiten | Konfiguration ändern, RIS/PACS-Seite debuggen |
| **2nd Level** | Broker-Betreuung im Haus (Radiologie-IT) | Konfiguration (Quellen, Ziele, Regeln, Stationen), Health-Findings abarbeiten, Spool/Dead Letters, Backup prüfen | HL7-Schnittstellen des RIS ändern |
| **3rd Level** | `⟨Lieferant/Integrator⟩` | Fehler im Broker, Updates, Schnittstellenfragen, Interop-Tests | Betrieb der Modalitäten |
| **RIS/PACS-Hersteller** | `⟨Hersteller⟩` | ihre Systeme, ihre Conformance Statements | den Broker |
| **Netzwerk** | `⟨Netzwerkbetrieb⟩` | IPs, VIP/Load Balancer (Hochverfügbarkeit), Firewall-Regeln | Broker-Konfiguration |

**Der wichtigste Satz für jede Ausschreibung:** Der Broker ist zwischen RIS und
Modalitäten der *einzige* Punkt, an dem beide Seiten sichtbar sind. Deshalb kann
das 2nd Level die meisten Fälle ohne Hersteller klären — der
[C-FIND-Test je Quelle](runbook.md#1-die-modalität-sieht-keine-arbeitsliste) und
die [Arbeitslisten-Vorschau](runbook.md#0-die-drei-werkzeuge-die-fast-alles-beantworten)
zeigen, ob die Quelle oder die Modalität das Problem ist.

## 2. Was der Broker für den Support beiträgt

Diese Liste ist der Grund, warum ein 1st Level überhaupt mitspielen kann — sie
ist bewusst konkret (jede Zeile ein Aufruf, kein Versprechen):

| Fähigkeit | Wo | Wofür im Support |
|---|---|---|
| Health-Findings mit Ursache und Fix-Link | `GET /api/v1/health/config`, Seite *MWL Broker* | Fehlkonfiguration erkennen, **bevor** eine Modalität anruft |
| 18 Alarmregeln + Grafana-Dashboard | `deploy/monitoring/` | Alarm → Runbook-Abschnitt (§4 unten) |
| Runbook mit den fünf echten Störungen | [`runbook.md`](runbook.md) | 1st-Level-Anleitung mit echten Befehlen |
| C-ECHO-Matrix (Quellen *und* Ziele) | Seite *MWL Broker* | „Wer ist gerade nicht erreichbar?" |
| C-FIND-Test je Quelle | Seite *Upstream sources* | „Liefert dieses RIS überhaupt eine Arbeitsliste?" |
| Arbeitslisten-Vorschau (mehrere Stationen) | Seite *Stationsregeln* | „Warum sieht die CT nichts?" ohne Änderung |
| Simulation (Routing, Modify-Regeln) | Seite *MWL Broker* → *Fall prüfen* | Auswirkung einer Regel prüfen, **bevor** sie greift |
| Änderungsprotokoll mit Rollback | Seite *Änderungsprotokoll* | „Was wurde gestern geändert?" + zurücknehmen |
| Konfigurations-Export/-Import (Dry-Run) | `GET/POST /api/v1/config/*` | Stand sichern, auf Testsystem nachstellen, Diff sehen |
| Query-/Store-Log (PHI-frei) | Seiten *MWL Broker*, *Store-Warteschlange* | „Kam die Abfrage an? Wurde das Bild weitergeleitet?" |
| HL7-Nachrichtenprotokoll + Replay | Seite *Lokale Worklist* | „Hat das RIS den Auftrag geschickt?" — und erneut anwenden |
| Spool-Seite: Retry je Eintrag, Verwerfen **mit Begründung** | Seite *Store-Warteschlange* | PACS-Ausfall nacharbeiten, ohne Bilder zu verlieren |
| Versionsnummer + Instanzname | `GET /api/v1/status` | „Welcher Build läuft? Welche Instanz antwortet?" |
| OpenAPI/Swagger | `/docs`, `/openapi.json` | Integrationsfragen ohne Rückfrage klären |
| Backup mit geprüftem Round-Trip | `deploy/backup.sh`, `deploy/backup-roundtrip-test.sh` | Wiederherstellung ist geübt, nicht gehofft |

## 3. Störungsklassen (Vorschlag)

Die Klasse richtet sich nach der **klinischen** Wirkung, nicht nach der Technik:

| Klasse | Wirkung | Beispiele | Reaktion (Vorschlag) |
|---|---|---|---|
| **S1** | Modalitäten bekommen **keine** Arbeitsliste; Betrieb steht | Broker down, alle Quellen down, DICOM-Port nicht erreichbar | `⟨15 min⟩` annehmen, `⟨1 h⟩` bis Entlastung, Meldung an die Radiologie |
| **S2** | Teilausfall: eine Quelle, ein Ziel, ein Spool-Rückstand | `MWLSourceDown`, `MWLTargetDown`, `MWLSpoolDeadLetters` | `⟨30 min⟩` annehmen, `⟨4 h⟩` bis Entlastung |
| **S3** | Degradiert, aber arbeitsfähig | Cache liefert (`MWLQueriesFromCache`), langsame Abfragen, MPPS-Rückmeldung stockt | `⟨4 h⟩` annehmen, nächster Werktag |
| **S4** | Komfort, Doku, Fragen | Zertifikat läuft ab (`MWLCertificateExpiring`), Konfigurationswarnung, Schulungsfrage | `⟨1 Arbeitstag⟩` |

`⟨Rufbereitschaft: ja/nein⟩` · `⟨Servicedesk-Zeiten⟩` · `⟨Wartungsfenster⟩` ·
`⟨Eskalationsweg: 1st → 2nd → 3rd, Telefonnummern⟩`

## 4. Alarm → Reaktion

Jede Regel aus `deploy/monitoring/prometheus-rules.yml` — ein Test hält diese
Tabelle mit der Datei zusammen, damit sie nicht auseinanderläuft.

| Alarm | Schwere | Erste Maßnahme | Runbook |
|---|---|---|---|
| `MWLBrokerDown` | critical | Container/Prozess prüfen, Logs, `docker compose ps` | [§5](runbook.md#5-der-broker-antwortet-nicht--500er) |
| `MWLBrokerHeartbeatStale` | warning | Läuft der Prozess noch? Datenbank beschreibbar? | [§6b](runbook.md#6b-eine-instanz-ist-weg--umschalten) |
| `MWLSourceDown` | critical | C-ECHO/C-FIND-Test je Quelle, RIS-Seite verständigen | [§2](runbook.md#2-eine-quelle-ris-antwortet-nicht) |
| `MWLTargetDown` | critical | C-ECHO auf das Ziel, Bilder laufen in den Spool (nicht verloren) | [§3](runbook.md#3-bilder-kommen-nicht-im-pacs-an) |
| `MWLBreakerOpen` | warning | Quelle ist übersprungen (3 Fehler) — Ursache beheben, Breaker zurücksetzen | [§2](runbook.md#2-eine-quelle-ris-antwortet-nicht) |
| `MWLQueriesFailing` | warning | Quellen und Timeouts prüfen, Query-Log ansehen | [§1](runbook.md#1-die-modalität-sieht-keine-arbeitsliste) |
| `MWLQueriesFromCache` | warning | Cache ist die Ausfallbrücke — Quelle prüfen, Stale-Fenster im Blick | [§1](runbook.md#1-die-modalität-sieht-keine-arbeitsliste) |
| `MWLSlowQueries` | warning | Quelle langsam? `upstream_timeout_s`, Last auf der Quelle | [§5](runbook.md#5-der-broker-antwortet-nicht--500er) |
| `MWLSpoolGrowing` | warning | Ziel erreichbar? Rückstand beobachten | [§3](runbook.md#3-bilder-kommen-nicht-im-pacs-an) |
| `MWLSpoolFull` | critical | Bilder werden **abgewiesen** — Ziel sofort prüfen, Budget/Platte | [§3](runbook.md#3-bilder-kommen-nicht-im-pacs-an) |
| `MWLSpoolDeadLetters` | critical | Ein Bild hat aufgegeben: Ursache im Eintrag, Retry oder Verwerfen mit Begründung | [§3](runbook.md#3-bilder-kommen-nicht-im-pacs-an) |
| `MWLSpoolOldest` | warning | Ältestes Bild wartet > 1 h — Ziel/Routing prüfen | [§3](runbook.md#3-bilder-kommen-nicht-im-pacs-an) |
| `MWLMppsNotReported` | warning | Modalität meldet Schritte, Rückmeldung stockt — RIS-Seite | [§4](runbook.md#4-das-ris-bekommt-keine-statusmeldungen-mpps) |
| `MWLMppsForwardFailing` | warning | MLLP/Webhook zum RIS prüfen, `POST /mpps/forward-pending` | [§4](runbook.md#4-das-ris-bekommt-keine-statusmeldungen-mpps) |
| `MWLConfigError` | warning | Health-Panel: Befund lesen, Fix-Link folgen | [§0](runbook.md#0-die-drei-werkzeuge-die-fast-alles-beantworten) |
| `MWLCertificateExpiring` | warning | Zertifikat erneuern (TLS-Karte), **vor** dem Ablauf | [§9](runbook.md#9-wo-man-nachsieht-kurzliste) |
| `MWLAtnaDropping` | warning | Audit-Gegenstelle nicht erreichbar/zu langsam | [§9](runbook.md#9-wo-man-nachsieht-kurzliste) |
| `MWLNotifyFailing` | warning | Webhook-Ziel prüfen — sonst bleibt jeder andere Alarm unbemerkt | [§9](runbook.md#9-wo-man-nachsieht-kurzliste) |

## 5. Wartung und Änderungen

| Thema | Vorgehen |
|---|---|
| **Update** | [`runbook.md`](runbook.md#7-update-auf-eine-neue-version) — Image bauen, `./build.sh --health`, bei HA die Instanzen **nacheinander** (die zweite bedient währenddessen) |
| **Wartungsfenster** | Nicht nötig, wenn die HA-Instanz die Arbeit übernimmt; sonst `⟨Fenster⟩` — ein Neustart unterbricht laufende Assoziationen, keine Daten gehen verloren (Spool) |
| **Konfigurationsänderung** | Über die Oberfläche (jede Änderung wird protokolliert und ist rücknehmbar) — **vorher** die Simulation nutzen |
| **Sicherung** | `deploy/backup.sh` per Cron; Wiederherstellung regelmäßig mit `deploy/backup-roundtrip-test.sh` üben |
| **Zertifikate** | Ablauf wird im Health-Panel und per Alarm gemeldet (`MWLCertificateExpiring`) |
| **Änderungsnachweis** | Änderungsprotokoll (wer/wann/vorher/nachher) + Konfigurations-Export als Standsicherung |

## 6. Übergabe bei Inbetriebnahme

Diese Punkte gehören in ein Abnahmeprotokoll (Vorlage, vom Betreiber zu
vervollständigen) — jeder Punkt ist ein Befehl, kein Versprechen:

1. `./setup.sh --check` — Konfiguration, Ports, RBAC, TLS, Alarmierung; offene
   Punkte sind benannt.
2. `./ci-local.sh` — alle Suiten grün ([`security-and-validation.md`](security-and-validation.md)).
3. `./test-stack.sh` — ephemerer Stack inkl. C-FIND-Smoke, Playwright und
   Backup-Round-Trip.
4. `deploy/ha-smoke.sh` — falls HA genutzt wird: keine Doppelzustellung.
5. `⟨Alarmweg getestet: POST /api/v1/notify/test, Mail/Teams angekommen⟩`
6. `⟨Runbook an das Haus angepasst: Rufnummern, Eskalation, Zugänge⟩`
7. `⟨Schulung durchgeführt: siehe [`training.md`](training.md)⟩`
8. `⟨Sicherung eingerichtet und eine Wiederherstellung geübt⟩`

## 7. Was dieses Konzept nicht abdeckt

Ehrlich benannt, damit keine Ausschreibung mehr verspricht als möglich ist:

- **Keine 24/7-Zusage** — die steht im Vertrag des Betreibers, nicht hier.
- **Kein Vor-Ort-Service**, keine Hardware, keine Ersatzteile.
- **Kein Medizinprodukt-Support**: Die CE-Kennzeichnung nach MDR ist
  zurückgestellt ([`next-steps.md`](next-steps.md) C1). Damit gibt es auch keine
  Meldepflichten nach MDR/Vigilanz — und keinen Hersteller im Sinne des MPDG.
- **Keine Verantwortung für RIS/PACS/Modalitäten** und ihre Conformance
  Statements.
- **Kein Penetrationstest, keine IEC 81001-5-1-Zertifizierung** — was dafür
  fehlt, steht in [`security-and-validation.md`](security-and-validation.md) §6.
- **Der Broker ist Open Source (MIT)**: keine Lizenzkosten, keine
  Aktivierungscodes, kein Vendor-Lock — aber auch kein Supportanspruch aus der
  Lizenz.
