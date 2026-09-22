# Nächste Schritte

Stand: 22.09.2026 · Die fünf Sprints aus
[`commercial-comparison.md`](commercial-comparison.md) sind abgeschlossen
(MPPS, feldweiser Merge + HL7-Mapping, Conformance Statement, Statistik,
UPS-RS-Subset). Dieses Dokument plant, was danach sinnvoll ist — getrennt nach
**Funktion**, **Betrieb**, **Nachweisen** und **Beschaffung**, mit Aufwand und
Begründung.

> **Die billigen Punkte sind weg.** Was hier noch steht, ist entweder **groß**
> (F3, F4) oder **organisatorisch** (C1, C4, E1). Betriebsseitig ist der Broker
> mit B5 (Lasttest) und B1 (Hochverfügbarkeit) dort angekommen, wo er für ein
> Haus mit 100+ Modalitäten sein muss — offen bleibt, was außerhalb des Codes
> liegt: VIP/Load Balancer, Postgres-Failover und der Interop-Nachweis (E1).

## 1. Wo wir stehen (kurz)

| Fähigkeit | Stand |
|---|---|
| MWL C-FIND Fan-out/Merge/Dedupe, Stationsregeln, Transforms, Store-Routing + Spool, Cache-Ausfallbrücke | vorhanden |
| HL7 ORM (REST + MLLP), lokale Worklist, ATNA, DICOM-TLS/mTLS, RBAC, Änderungsprotokoll, Retention | vorhanden |
| **MPPS SCP + Status-Rückmeldung an das RIS** | vorhanden (Sprint 1) |
| **Feldweiser Merge + HL7→DICOM-Mapping** | vorhanden (Sprint 2) |
| **DICOM Conformance Statement + IHE-Aussage** | vorhanden (Sprint 3) |
| **Statistik/Reporting** | vorhanden (Sprint 4) |
| **UPS-RS** (Suche/Abruf/Anlegen/Status) | vorhanden, **Subset** (Sprint 5) |
| **IID** (Invoke Image Display, RAD-106) in der UI | vorhanden — OE3 öffnet den Viewer über den IHE-Einstiegspunkt (Study- **und** Patient-basiert) |
| **Auftragskontext** (`GET /orders/context`) | vorhanden — Korrelationsdienst für einen MADO-Manifest-Erzeuger |
| **MADO** (Manifest-basierter Zugriff) | **bewusst kein Akteur** — Content-Access ist PACS/VNA-Aufgabe; Einordnung und Berührungspunkte in der [IHE-Aussage §6](ihe-profile-statement.md#6-mado-manifest-based-access-to-dicom-objects--einordnung) |
| Werkzeuge: Vorschau, C-FIND-Test, Trockenläufe, Health, Bootstrap, Tests aller Ebenen | vorhanden |
| **Hochverfügbarkeit** | zweite Instanz (Profil `ha`) auf gemeinsamer DB und gemeinsamem Spool-Volume, atomarer Spool-Claim, Instanz-Heartbeat in UI + Health-Prüfung ([`ha.md`](ha.md)) |
| **Betriebsdokumente** | Runbook, Support-/SLA-Vorlage, Schulungsunterlagen — alle per Test an Code, Alarme, Skripte und Hilfeseiten gebunden |
| **Nachweise** | Conformance Statement und IHE-Aussage sind per Test an den Code gebunden, die Suiten dienen als Abnahmegrundlage, der **Lasttest** ist gefahren ([`loadtest.md`](loadtest.md)) — **der Interop-Nachweis mit Fremdsystemen fehlt** (E1) |

## 2. Funktionale Kandidaten

| # | Vorhaben | Warum | Aufwand |
|---|---|---|---|
| F1 | ~~MRN-Merge / Identifier-Reconciliation~~ — **erledigt**: `ADT^A40` und manueller Eintrag, rücknehmbar, wirkt auf Arbeitsliste **und** Routing-Herkunft (Kette zyklensicher). Offen: A24/A47-Links und PIX/PDQ | — | ✅ |
| F2a | ~~ADT `A08`/`A24`/`A47`, dazu `OMG^O19`~~ — **erledigt**: `A08` schreibt die Demografie der eigenen Arbeitslisten-Einträge um (nur die Felder, die die Nachricht trägt), `A24` speichert eine **Verknüpfung** (beide IDs bleiben gültig — es wird *nichts* umgeschrieben) und `A47` nimmt sie zurück. Beides über REST **und** MLLP; ein `A40` nach einem `A24` stuft zur Zusammenführung hoch. Offen: PIX/PDQ (siehe F2c) | — | ✅ |
| F2b | **Weitere Datenquellen ohne HL7**: GDT/BDT, strukturierte Textdateien | Praxen und Häuser ohne HL7-Schnittstelle (GDT ist der deutsche Sonderweg) | mittel (je Quelle ein Adapter) |
| F2c | **PIX/PDQ** (Patient-Index abfragen statt auf ADT warten) | **Kandidat, bewusst nicht gebaut.** Nur sinnvoll, wenn im Haus ein Patient-Index steht (PIX-/PDQ-Supplier) — sonst toter Code; viele Häuser senden stattdessen ADT, und das ist seit F2a abgedeckt. Überschneidet sich mit PIR: `A40` ist das *Ereignis*, PIX die *Abfrage*. Wenn gebaut, dann **FHIR zuerst** (PIXm/PDQm, ITI-83/78: HTTP+JSON statt MLLP+HL7-Builder) — die v2-Varianten (ITI-9/21) nur für ein Haus mit altem v2-Index. Einsatzorte wären: Demografie für lokale Einträge nachladen, ID-Auflösung als Fallback in der C-FIND-Antwort, Betreiber-Werkzeug „ID auflösen" | mittel (v2), klein-mittel (FHIR) |
| F3 | **UPS-RS vervollständigen**: Subscriptions/WebSocket-Events, vollständiger Attributsatz, Suche über Upstream | Für Clients, die den Standard voll ausreizen; heute bewusst als Grenze dokumentiert | groß |
| F4 | **Voraufnahmen-Prefetch** (relevante Voruntersuchungen auf Anforderung ziehen) | Radiologen brauchen Voraufnahmen am Befundplatz; heute Aufgabe von PACS/VNA | groß (eigenes Werkzeug) |
| F5 | **Tag-Morphing über Felder hinaus**: Sequenz-Operationen, Private Tags, Encoding-Transkodierung | Für Häuser mit exotischen Empfängern. **Getrennt halten:** Private Tags und Sequenzen sind machbar; Transkodierung widerspricht dem heutigen Statement („der Broker ändert keine Pixel") und ist die Stelle, an der man Bilddaten beschädigen kann — nur mit eigener Entscheidung | mittel |
| F6 | ~~MPPS N-GET (Status zurücklesen) und MPPS-Statistik je Modalität~~ — **erledigt**: N-GET über echte Assoziation geprüft, `by_modality` in `/mpps/stats` + in der Karte | — | ✅ |
| F7 | ~~Arbeitslisten-Vorschau für mehrere Stationen gleichzeitig~~ — **erledigt**: `POST /simulate/stations` + Matrix-Karte (sichtbare/verborgene Quellen je Station, Warnung bei leerer Liste) | — | ✅ |
| F8 | ~~Auftragskontext (Studie ↔ Auftrag)~~ — **erledigt**: `GET /orders/context?study_uid=…` (oder `?accession=…`) liefert Accession, SPS-ID, Station, Modalität, Herkunft, MPPS-Zustand und weitergeleitete Instanzen (PHI-frei) | — | ✅ |
| F9 | ~~IID (Invoke Image Display, RAD-106)~~ — **erledigt**: OE3 liefert `/oe3/IHEInvokeImageDisplay?requestType=STUDY&studyUID=…` (oder `accessionNumber=…`) bzw. `?requestType=PATIENT&patientID=…`; Study- und Patient-basiert, `mostRecentResults` berücksichtigt. Der eigene Viewer-Knopf benutzt denselben Weg | — | ✅ |

## 3. Betriebliche Kandidaten

| # | Vorhaben | Warum | Aufwand |
|---|---|---|---|
| B1 | ~~Hochverfügbarkeit~~ — **erledigt**: [`ha.md`](ha.md). Zweite Instanz auf gemeinsamer DB und gemeinsamem Spool-Volume (Compose-Profil `ha`), **atomarer Spool-Claim** (`FOR UPDATE SKIP LOCKED` + Lease), Instanz-Heartbeat mit Sichtbarkeit in UI und Health-Prüfung, Alarmregeln, Runbook-Kapitel, `deploy/ha-smoke.sh` als Live-Nachweis (24 Bilder, 12 + 12 zugestellt, **keine Doppellung**). Offen bleibt die Deployment-Seite: VIP/Load Balancer und Postgres-Failover liegen außerhalb des Brokers | — | ✅ |
| B2 | ~~Backup-Automatik~~ — **erledigt**: `deploy/backup.sh` (beide Datenbanken, Spool, `.env`, Prüfungen) + `deploy/backup-roundtrip-test.sh` (sichern → zerstören → wiederherstellen → prüfen), läuft bei jedem `./test-stack.sh` | — | ✅ |
| B3 | ~~Betriebshandbuch/Runbook~~ — **erledigt**: [`runbook.md`](runbook.md) („was tun, wenn …“ mit echten Befehlen, Eskalationsgrenzen, Update-Ablauf) | — | ✅ |
| B4 | ~~Monitoring-Vorlage~~ — **erledigt**: `deploy/monitoring/prometheus-rules.yml` (18 Regeln) + `grafana-dashboard.json` (14 Panels), durch `test_monitoring_config.py` an die echten Metriknamen gebunden | — | ✅ |
| B5 | ~~Lasttest~~ — **erledigt**: [`loadtest.md`](loadtest.md) — Harness (`scripts/loadtest.py`), Messwerte, Grenzen. **Zwei echte Nebenläufigkeitsfehler gefunden und behoben** (Breaker-Zeile und Cache-Snapshot kollidierten unter parallelen Abfragen; eine Arbeitslisten-Abfrage kam als DIMSE-Fehler zurück), das Assoziationslimit als harte Grenze belegt. Offen: Wiederholung auf der Zielhardware und ein Soak-Test | — | ✅ |
| B6 | ~~Selbstüberwachung~~ — **erledigt**: Health-Findings `spool_disk_low`/`spool_disk_tight`/`spool_dir_unusable`/`db_slow` + Alarmregel | — | ✅ |

### B1 — was die Vorbedingung war, und was daraus wurde

„Zweite Instanz + gemeinsame DB" klang nach einem Compose-Eintrag, war aber
keiner. Die drei Punkte, die im Code geprüft wurden, sind jetzt abgearbeitet:

- **Der Spool hatte kein Claiming.** `spool.due_items()` wählte nur nach Status
  und Fälligkeit — zwei Instanzen hätten dieselbe Zeile gezogen und dasselbe Bild
  zweimal gesendet. Jetzt gibt es `spool.claim_items` (atomar,
  `FOR UPDATE SKIP LOCKED` + Lease), der Worker benutzt es, und
  `deploy/ha-smoke.sh` belegt es am laufenden System.
- **Geteilter und lokaler Zustand waren gemischt.** `source_breaker` und der neue
  Instanz-Heartbeat liegen in der Datenbank; `echo.ECHO_STATUS` bleibt bewusst
  pro Instanz (jede prüft ihre eigenen Verbindungen) — beides steht in
  [`ha.md`](ha.md) §2, damit niemand raten muss.
- **Der Endpunkt gehört zum Vertrag.** AET und Port stehen im
  [Conformance Statement](dicom-conformance-statement.md); wie die Modalitäten
  die aktive Instanz finden (schwebende IP, TCP-Load-Balancer, zweiter AET), ist
  in [`ha.md`](ha.md) §4 dokumentiert — und `/healthz/ready` ist genau der
  Health-Check dafür.

**Was außerhalb bleibt:** VIP/Load Balancer einrichten, Postgres-Failover, ein
Lasttest *mit* zwei Instanzen. Der Broker kann seine eigene Adresse nicht
bewegen — das ist Netzwerk- und Deployment-Aufgabe.

## 4. Nachweise

| # | Vorhaben | Warum | Aufwand |
|---|---|---|---|
| E1a | ~~Interop-Nachweis, Teil 1: gegen **Fremdsoftware**~~ — **erledigt**: [`interop.md`](interop.md) + [`interop-tools.md`](interop-tools.md) (Werkzeug-Lückenanalyse). `deploy/interop-test.sh` mit **15 Prüfungen** gegen **DCMTK** (fremdes RIS, fremde Modalität, fremdes PACS) und **dcm4che** (fremder MPPS-SCU, fremder HL7-Sender/-Empfänger). **Sieben echte Fehler gefunden** — u. a. mehrwertige Attribute, die die ganze Antwort kosteten; MPPS ohne SOP-Instanz-UID wurde abgelehnt; unser ACK war um zwei Felder verschoben; MSH-6 fehlte; MSH-9 wurde zu streng verglichen; der MLLP-Schalter war wirkungslos | — | ✅ |
| E1b | **Interop-Nachweis, Teil 2: HL7-Validator + Connectathon/Projectathon** — Gazelle HL7 Validator für die Nachrichten (`deploy/interop/samples/` liegt bereit), Order Manager als fremde SWF-Gegenseite, echte Modalität + fremdes RIS | Die HL7-Seite ist bisher nur von *unserem* Parser geprüft, und **kein echter Modalitäten-Client, kein fremdes RIS** war je am Broker. Gazelle ist Test-Management/Validierung, **nicht** die Gegenseite (das `framework`-Repo ist eine Java-Bibliothek zum Bauen eigener Tools, ein lokaler Test-Bed-Aufbau läuft auf EOL-Software — beides nicht sinnvoll). Braucht einen IHE-Zugang bzw. einen Termin | organisatorisch (Vorbereitung klein) |

Für die Vorbereitung ist wenig zu bauen: die Testfälle existieren schon
(C-FIND-Matching, MPPS-Zustellung, TLS, SPS-Status), es fehlt der Gegenüber. Ein
Connectathon ist genau der Ort, an dem die Aussage aus §2 der
[IHE-Aussage](ihe-profile-statement.md) geprüft wird — und der Ort, an dem
Matching-Feinheiten auffallen, die kein Mock nachbildet. Teil 1 (DICOM gegen
DCMTK) ist gefahren; Teil 2 braucht einen IHE-Zugang.

## 5. Beschaffung und Compliance

| # | Vorhaben | Warum | Aufwand |
|---|---|---|---|
| C1 | **CE-Kennzeichnung nach MDR** (auf Wunsch des Betreibers zurückgestellt) als Medizinprodukt, IEC 62304-Lebenszyklus, ISO 14971-Risikodossier | Ohne das ist kein Verkauf/Einsatz als Medizinprodukt in der EU möglich — der eigentliche Unterschied zu kommerziellen Produkten | organisatorisch, groß |
| C2 | ~~Validierungsdokumentation~~ — **erledigt** als Ablaufbeschreibung (§4 in `security-and-validation.md`: Suiten als Abnahmegrundlage, drei Betriebsfälle, Ablage von Datum/Version/Findings). Formale Abzeichnung bleibt Sache des Betreibers | — | ✅ |
| C3 | ~~Cybersecurity-Dokumentation~~ — **erledigt** (ohne Zertifizierungsanspruch): [`security-and-validation.md`](security-and-validation.md) — Schutzbedarf/Datenfluss, Härtungsliste, **bekannte Grenzen**, Validierungsablauf, Patchprozess, was für einen echten Nachweis fehlt (Pentest, IEC 81001-5-1, Lasttest, DSFA) | — | ✅ |
| C4 | ~~Support-/SLA-Konzept + Schulungsunterlagen~~ — **erledigt**: [`support-and-sla.md`](support-and-sla.md) (Rollen, Störungsklassen S1–S4 mit Platzhaltern für die Zusagen, **Alarm → Maßnahme**-Tabelle, Wartung, Übergabe-Checkliste, was nicht abgedeckt ist) und [`training.md`](training.md) (Zielgruppen, Abläufe, **12 Übungen mit überprüfbarem Ergebnis**, Abnahmekriterien, Kurztest). Beide an den Code gebunden: `tests/test_support_docs.py` prüft Alarmnamen, Runbook-Anker, Skripte und die Hilfeseiten der Oberfläche | — | ✅ |
| C5 | **IHE MADO / EHDS** — Beobachtungsposten (auf Wunsch: nur dokumentieren) | MADO v1.0.0 ist **trial-use** (publiziert 09/2026), die EHDS-Sekundärnutzung greift 2029. Der Broker ist **kein** MADO-Akteur (Content-Access vs. Workflow) — die Einordnung, die Berührungspunkte (Auftragskontext, WADO-RS im Orthanc) und die Lücke stehen in der [IHE-Aussage §6](ihe-profile-statement.md#6-mado-manifest-based-access-to-dicom-objects--einordnung). Umsetzung nur bei konkreter Kundenanforderung | organisatorisch, groß |

## 6. Empfohlene Reihenfolge

1. ~~**B2 + B3 + B4** (klein, sofort nutzbar: Backup, Runbook, Alarme)~~ — **erledigt**.
2. ~~**F6 + F7 + B6** (klein): schnell sichtbarer Nutzen für Betreiber~~ — **erledigt**.
3. ~~**F1 (MRN-Merge)** — die größte verbleibende funktionale Lücke~~ — **erledigt**.
4. ~~**C2 + C3** — Vorbereitung der Beschaffung~~ — **erledigt** (C1/MDR bewusst zurückgestellt).
5. ~~**F8 + F9 + C5** (klein): Auftragskontext, IID und die MADO-Einordnung~~ — **erledigt**.
6. ~~**B5 (Lasttest)**~~ — **erledigt**: [`loadtest.md`](loadtest.md) liefert die
   Dimensionierungszahl *und* hat zwei Nebenläufigkeitsfehler aufgedeckt, die
   jetzt behoben sind. Offen bleibt die Wiederholung auf der Zielhardware.
7. **E1 (Interop-Nachweis)** — der einzige Weg, aus dem Statement einen Beweis
   zu machen. Beantwortet außerdem die im Lasttest offen gebliebene Frage, wo die
   ~90 ms pro C-FIND-Runde herkommen (eigener Client oder Gegenstelle).
8. ~~**B1 (Hochverfügbarkeit)**~~ — **erledigt**: Design-Vorlauf aus §3 umgesetzt
   (Claim + geteilter Zustand + Endpunkt-Dokumentation), nachgewiesen mit
   `deploy/ha-smoke.sh`.
9. ~~**F2a (ADT `A08`/`A24`/`A47`)**~~ — **erledigt**: die PIR-Lücke ist
    geschlossen, Verknüpfung und Zusammenführung sind sauber getrennt.
10. ~~**C4 (SLA/Schulungsunterlagen)**~~ — **erledigt**: [`support-and-sla.md`](support-and-sla.md)
    und [`training.md`](training.md), beide per Test an Alarme, Runbook-Kapitel,
    Skripte und die Hilfeseiten gebunden. Was bleibt, ist Betreiberarbeit:
    Reaktionszeiten und Eskalationswege ausfüllen.
11. **F2b (GDT/BDT)**, **F5 (Tag-Morphing)** — nach Bedarf, je Haus.
12. **F3/F4** nur, wenn ein konkreter Kunde sie verlangt. **C1** bleibt
    zurückgestellt, **C5** bleibt Beobachtungsposten.

## 7. Was bewusst außerhalb bleibt

Prefetch von Voraufnahmen, Transkodierung, De-Identifikation (PS3.15),
Storage Commitment, C-MOVE/C-GET, Print — das sind Aufgaben von PACS, VNA oder
einem Router. Sie sind im
[Conformance Statement §9](dicom-conformance-statement.md) mit Begründung
aufgeführt.
