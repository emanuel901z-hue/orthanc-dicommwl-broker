# Nächste Schritte

Stand: 22.09.2026 · Die fünf Sprints aus
[`commercial-comparison.md`](commercial-comparison.md) sind abgeschlossen
(MPPS, feldweiser Merge + HL7-Mapping, Conformance Statement, Statistik,
UPS-RS-Subset). Dieses Dokument plant, was danach sinnvoll ist — getrennt nach
**Funktion**, **Betrieb**, **Nachweisen** und **Beschaffung**, mit Aufwand und
Begründung.

> **Die billigen Punkte sind weg.** Was hier noch steht, ist entweder **groß**
> (B1, F3, F4) oder **organisatorisch** (C1, C4, E1). Die nächste Stufe beginnt
> deshalb nicht mit dem größten Vorhaben, sondern mit dem, das die meisten
> anderen freischaltet — und B1 ist keine Compose-Änderung (siehe §3).## 1. Wo wir stehen (kurz)

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
| **Nachweise** | Conformance Statement und IHE-Aussage sind per Test an den Code gebunden, die Suiten dienen als Abnahmegrundlage, der **Lasttest** ist gefahren ([`loadtest.md`](loadtest.md)) — **der Interop-Nachweis mit Fremdsystemen fehlt** (E1) |

## 2. Funktionale Kandidaten

| # | Vorhaben | Warum | Aufwand |
|---|---|---|---|
| F1 | ~~MRN-Merge / Identifier-Reconciliation~~ — **erledigt**: `ADT^A40` und manueller Eintrag, rücknehmbar, wirkt auf Arbeitsliste **und** Routing-Herkunft (Kette zyklensicher). Offen: A24/A47-Links und PIX/PDQ | — | ✅ |
| F2a | **ADT `A08`/`A24`/`A47`** (Patientendaten geändert, Link/Unlink) | `A08` ist das **häufigste** reale ADT-Event — heute ist nur `A40` abgedeckt. Ein Haus, das `A08` nicht weiterleitet, arbeitet mit veralteten Demografiedaten weiter; `A24`/`A47` schließen die in der [IHE-Aussage](ihe-profile-statement.md) benannte PIR-Lücke | klein (Erweiterung von `hl7.py`/`merges.py`) |
| F2b | **Weitere Datenquellen ohne HL7**: GDT/BDT, strukturierte Textdateien, `OMG` | Praxen und Häuser ohne HL7-Schnittstelle (GDT ist der deutsche Sonderweg); `OMG` für Auftragsänderungen | mittel (je Quelle ein Adapter) |
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
| B1 | **Hochverfügbarkeit**: zweite Instanz + gemeinsame DB/Spool-Volume, Health-basiertes Umschalten, Runbook | Ein einzelner Broker ist ein Single Point of Failure für alle Modalitäten. **Vorbedingung siehe unten** — erst das Design, dann die zweite Instanz | groß |
| B2 | ~~Backup-Automatik~~ — **erledigt**: `deploy/backup.sh` (beide Datenbanken, Spool, `.env`, Prüfungen) + `deploy/backup-roundtrip-test.sh` (sichern → zerstören → wiederherstellen → prüfen), läuft bei jedem `./test-stack.sh` | — | ✅ |
| B3 | ~~Betriebshandbuch/Runbook~~ — **erledigt**: [`runbook.md`](runbook.md) („was tun, wenn …“ mit echten Befehlen, Eskalationsgrenzen, Update-Ablauf) | — | ✅ |
| B4 | ~~Monitoring-Vorlage~~ — **erledigt**: `deploy/monitoring/prometheus-rules.yml` (17 Regeln) + `grafana-dashboard.json` (14 Panels), durch `test_monitoring_config.py` an die echten Metriknamen gebunden | — | ✅ |
| B5 | ~~Lasttest~~ — **erledigt**: [`loadtest.md`](loadtest.md) — Harness (`scripts/loadtest.py`), Messwerte, Grenzen. **Zwei echte Nebenläufigkeitsfehler gefunden und behoben** (Breaker-Zeile und Cache-Snapshot kollidierten unter parallelen Abfragen; eine Arbeitslisten-Abfrage kam als DIMSE-Fehler zurück), das Assoziationslimit als harte Grenze belegt. Offen: Wiederholung auf der Zielhardware und ein Soak-Test | — | ✅ |
| B6 | ~~Selbstüberwachung~~ — **erledigt**: Health-Findings `spool_disk_low`/`spool_disk_tight`/`spool_dir_unusable`/`db_slow` + Alarmregel | — | ✅ |

### B1 — Vorbedingung: erst das Design, dann die zweite Instanz

„Zweite Instanz + gemeinsame DB" klingt nach einem Compose-Eintrag. Im Code
geprüft ist es keiner:

- **Der Spool hat kein Claiming.** `spool.due_items()` wählt nur nach Status und
  Fälligkeit (`next_attempt_at`) — ohne Lease, ohne `FOR UPDATE SKIP LOCKED`.
  Zwei Instanzen auf derselben DB ziehen dieselbe Zeile und senden **beide** an
  das PACS. `spool.is_duplicate` schützt am *Eingang* (die Modalität wiederholt
  den C-STORE), nicht bei der Zustellung. Ohne Claiming erzeugt HA genau die
  Duplikate, die der Spool verhindern soll.
- **Geteilter und lokaler Zustand gemischt.** `source_breaker` liegt in der DB
  (teilbar, gut), `echo.ECHO_STATUS` ist ein Modul-Dict im Prozess — zwei
  Instanzen melden unterschiedliche Health für dieselben Quellen.
- **Der Endpunkt gehört zum Vertrag.** AET `MWLBROKER` und Port stehen im
  [Conformance Statement](dicom-conformance-statement.md). Wie die Modalitäten
  die aktive Instanz finden (schwebende IP, zweite AET, Load-Balancer), ist eine
  Deployment-Entscheidung — und muss dokumentiert sein, sonst stimmt das
  Statement nicht mehr.

Reihenfolge deshalb: (1) Zustell-Claim (Lease-Spalte + Alembic-Revision),
(2) entscheiden, welcher Zustand geteilt wird und welcher bewusst pro Instanz
bleibt, (3) Endpunkt-Strategie + Runbook-Ergänzung, (4) erst dann die zweite
Instanz und das Health-basierte Umschalten.

## 4. Nachweise

| # | Vorhaben | Warum | Aufwand |
|---|---|---|---|
| E1 | **Interop-Nachweis mit Fremdsystemen** — IHE-Connectathon/Projectathon oder ein Vendor-Test mit einer echten Modalität und einem echten RIS | Alle DIMSE-Gegenstellen sind heute **unser eigener Code**: `mock-ris-a/b` und `dicom-peer` bauen aus `./mwl-broker`, `tests/test_dimse_integration.py` nutzt `mwl_broker.mock_ris`; fremd ist nur Orthanc als C-STORE-Ziel. **Kein echter Modalitäten-Client, kein fremdes RIS war je am Broker.** Das Conformance Statement ist per Test an *unseren* Code gebunden — belegt ist es damit nicht | organisatorisch (Vorbereitung klein, Termin-/Reiseaufwand) |

Für die Vorbereitung ist wenig zu bauen: die Testfälle existieren schon
(C-FIND-Matching, MPPS-Zustellung, TLS, SPS-Status), es fehlt der Gegenüber. Ein
Connectathon ist genau der Ort, an dem die Aussage aus §2 der
[IHE-Aussage](ihe-profile-statement.md) geprüft wird — und der Ort, an dem
Matching-Feinheiten auffallen, die kein Mock nachbildet.

## 5. Beschaffung und Compliance

| # | Vorhaben | Warum | Aufwand |
|---|---|---|---|
| C1 | **CE-Kennzeichnung nach MDR** (auf Wunsch des Betreibers zurückgestellt) als Medizinprodukt, IEC 62304-Lebenszyklus, ISO 14971-Risikodossier | Ohne das ist kein Verkauf/Einsatz als Medizinprodukt in der EU möglich — der eigentliche Unterschied zu kommerziellen Produkten | organisatorisch, groß |
| C2 | ~~Validierungsdokumentation~~ — **erledigt** als Ablaufbeschreibung (§4 in `security-and-validation.md`: Suiten als Abnahmegrundlage, drei Betriebsfälle, Ablage von Datum/Version/Findings). Formale Abzeichnung bleibt Sache des Betreibers | — | ✅ |
| C3 | ~~Cybersecurity-Dokumentation~~ — **erledigt** (ohne Zertifizierungsanspruch): [`security-and-validation.md`](security-and-validation.md) — Schutzbedarf/Datenfluss, Härtungsliste, **bekannte Grenzen**, Validierungsablauf, Patchprozess, was für einen echten Nachweis fehlt (Pentest, IEC 81001-5-1, Lasttest, DSFA) | — | ✅ |
| C4 | **Support-/SLA-Konzept**, Schulungsunterlagen | Teil jeder Ausschreibung. Die „Was ist das?"-Hilfe je Seite (`PageHelp`), die MFA-Reise und das Runbook sind schon die halbe Miete — es fehlt die Form (Reaktionszeiten, Eskalation, Schulungsablauf) | organisatorisch |
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
8. **B1 (Hochverfügbarkeit)** — mit dem Design-Vorlauf aus §3; erst danach die
   zweite Instanz.
9. **F2a (ADT `A08`/`A24`/`A47`)** — klein, schließt die PIR-Lücke.
10. **C4 (SLA/Schulungsunterlagen)** — organisatorisch, aber Eintrittskarte für
    jede Ausschreibung.
11. **F2b (GDT/BDT)**, **F5 (Tag-Morphing)** — nach Bedarf, je Haus.
12. **F3/F4** nur, wenn ein konkreter Kunde sie verlangt. **C1** bleibt
    zurückgestellt, **C5** bleibt Beobachtungsposten.

## 7. Was bewusst außerhalb bleibt

Prefetch von Voraufnahmen, Transkodierung, De-Identifikation (PS3.15),
Storage Commitment, C-MOVE/C-GET, Print — das sind Aufgaben von PACS, VNA oder
einem Router. Sie sind im
[Conformance Statement §9](dicom-conformance-statement.md) mit Begründung
aufgeführt.
