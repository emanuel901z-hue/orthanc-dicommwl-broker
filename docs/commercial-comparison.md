# Kommerzielle MWL-Broker im Vergleich — und was wir daraus bauen

Kurzrecherche (Stand 21.09.2026) zu marktüblichen Worklist-Brokern und
DICOM-Routern, mit ehrlicher Gegenüberstellung zum eigenen Funktionsumfang und
einer priorisierten Lückenliste. Die daraus abgeleiteten Sprints sind unten
verlinkt; der Umsetzungsstand steht am Ende jeder Sprint-Sektion.

## 1. Was verglichen wurde

| Produkt / Standard | Quelle |
|---|---|
| **Laurel Bridge Waypoint** (Encounter & Modality Worklist Manager) | laurelbridge.com/products/waypoint |
| **Laurel Bridge Navigator** (Prefetch von Voraufnahmen), **Compass** (Routing) | laurelbridge.com/products/navigator, /solutions/prefetching-solution |
| **Dicom Systems Unifier** (enterprise MWL + HL7-Broker + Proxy) | dcmsys.com/solutions/dicom-modality-worklist |
| **ETIAM IDeal Broker** | imgsol.com, ETIAM-Broschüre |
| **Health Comm IDeal** (DICOM Worklist-Broker, deutscher Markt) | health-comm.de/ideal-dicom-worklist-broker |
| **iQ-WORKLIST** (iq-image, deutscher Markt) | iq-image.com/product/iq-worklist |
| **medigration ImageBroker** (bender gruppe) | bendergruppe.com (Conformance Statement 4.2) |
| **worklist-server.de** (GDT-Worklist-Server) | worklist-server.de |
| **Standards**: MPPS (PS3.4 Annex F), Unified Procedure Step + **UPS-RS** (PS3.4 Annex CC / PS3.18 §11), IHE **Scheduled Workflow (SWF)**, **Patient Information Reconciliation (PIR)** | dicomstandard.org, dicom.nema.org |

## 2. Der eine große funktionale Unterschied: der Rückkanal

Alle kommerziellen Produkte sprechen **MPPS** und melden den Status **zurück**
ins KIS/RIS:

> „Returns examination statuses (converted from DICOM MPPS to HL7) to
> information systems." — ETIAM IDeal Broker
>
> „MPPS-Statusmeldungen der Modalitäten werden in entsprechende HL7-Nachrichten
> umgewandelt und an den Einsender des Auftrags zurückgeschickt. Damit kann der
> Auftrag im KIS/PVS automatisch abgeschlossen werden." — Health Comm IDeal
>
> „fully automated workflow through MPPS … can read radiation dose, billing
> data, study status, series or image data and provide it to the feeding
> information system like HIS, RIS or EMR." — iQ-WORKLIST

Wir liefern bislang nur **aus** (Pull). Ohne MPPS bleibt der Auftrag im RIS
„offen", wenn die Modalität ihn nicht selbst zurückmeldet.

## 3. Gegenüberstellung

| Fähigkeit | Kommerziell | Eigener Stand |
|---|---|---|
| MWL C-FIND, Fan-out, Merge, Dedupe | ✓ | ✓ |
| Regeln je Station/Modalität, Prioritäten | ✓ | ✓ |
| **MPPS SCP** (N-CREATE/N-SET) | ✓ alle | ✗ → **Sprint 1** |
| **MPPS → HL7 zurück** (Auftrag schließen) | ✓ alle | ✗ → **Sprint 1** |
| **UPS / UPS-RS** (DICOMweb-Worklist, Subscriptions) | ✓ Waypoint, Unifier | ✗ → **Sprint 5** |
| **IHE PIR / Identifier-Merge** (mehrere MRNs) | ✓ ETIAM, Health Comm | ✗ (offen) |
| **Storage Commitment / Study Content Notification** | ✓ medigration | ✗ (Router-Thema) |
| HL7 **ORM** | ✓ | ✓ (REST + MLLP) |
| HL7 **ADT/OMG**, **GDT/BDT**, proprietäre Textdateien | ✓ iQ-WORKLIST, worklist-server.de | ✗ (offen) |
| **Frei konfigurierbares Mapping** HL7→DICOM-Tags | ✓ Waypoint, iQ-WORKLIST | teilweise (feste Operatoren) → **Sprint 2** |
| **Feldweiser Merge** (Demografie von A, Auftrag von B) | ✓ | ✗ → **Sprint 2** |
| Prefetch **relevanter Voraufnahmen** (STAT/ED/Stroke, Body Part) | ✓ Navigator | ✗ (PACS-/Archiv-Thema) |
| **Transcoding, De-Identifikation (PS3.15), Pixel-Morphing** | ✓ Compass/Unifier | ✗ (Router-Thema) |
| **Hochverfügbarkeit/Cluster, Multi-Site** | ✓ (iQ-WORKLIST „concurrent licensing", medigration „Ausfallkonzepte") | ✗ (Einzelinstanz + Spool) |
| **Statistik/Reporting** (Auslastung je System/Modalität) | ✓ ETIAM, iQ-WORKLIST | teilweise → **Sprint 4** |
| Lizenz nach Modalitätszahl | ✓ (2/5/10/unbegrenzt) | Open Source |
| **DICOM Conformance Statement** | ✓ Pflichtdokument | ✗ → **Sprint 3** |
| **CE-Kennzeichnung (MDR)**, IEC 62304, ISO 14971, Validierung | ✓ | ✗ (organisatorisch, nicht Code) |

## 4. Wo wir mehr haben als die Kommerziellen

In keiner der eingesehenen Produktbeschreibungen fanden sich:

- **Vorschau der zusammengeführten Arbeitsliste** („was bekommt das Gerät
  tatsächlich?") — läuft über die echte Aggregation.
- **C-FIND-Test je Quelle** („liefert dieses RIS überhaupt Arbeitslisten?").
- **Trockenlauf für Routing und Tag-Änderungen**, **Stations-Vorschau**.
- **Änderungsprotokoll mit Rollback** und Vorher/Nachher-Diff.
- **Cache als Ausfallbrücke** (Modalitäten arbeiten weiter, wenn das RIS
  ausfällt) — kommerziell meist nur Retry/Queue.
- **Offene API** (OpenAPI/Swagger, 79 Operationen), Prometheus-Metriken,
  reproduzierbares Deployment, geführter Produktiv-Bootstrap
  (`./setup.sh`), PHI-freie Logs, ATNA-Export, RBAC mit Nur-Lese-Diagnose.

## 5. Priorisierte Lücken (Grundlage der Sprints)

| # | Lücke | Warum sie weh tut | Sprint |
|---|---|---|---|
| 1 | **MPPS SCP + Status-Rückmeldung** | Ohne sie bleiben Aufträge im RIS offen — die Kern-Erwartung an einen MWL-Broker | Sprint 1 |
| 2 | **Feldweiser Merge + Mapping-Vorlagen** | Kommerzielle mischen Demografie von Quelle A mit Auftragsdaten von B; wir wählen nur „wer gewinnt" | Sprint 2 |
| 3 | **DICOM Conformance Statement + IHE-Profil-Aussage** | Ohne dieses Dokument geht keine formale Beschaffung | Sprint 3 |
| 4 | **Statistik/Reporting** | Betreiber und QM fragen nach Auslastung und Fehlerquoten; die Daten liegen schon in den Logs | Sprint 4 |
| 5 | **UPS-RS** (DICOMweb-Worklist) | Neue Modalitäten/PACS fragen zunehmend REST statt DIMSE | Sprint 5 |

Bewusst **außerhalb** des Scopes (Router-/Archiv-Aufgaben): Prefetch von
Voraufnahmen, Transcoding, De-Identifikation, Storage Commitment.

## 6. Sprint-Plan und Stand

Die Lücken aus Abschnitt 5 werden in fünf Sprints geschlossen. Der Status wird
nach jedem Sprint aktualisiert; jeder Sprint endet mit Tests, vollständiger
Verifikation (`./ci-local.sh`) und einem Commit — ohne Regression.

| Sprint | Inhalt | Status |
|---|---|---|
| 1 | **MPPS SCP + Status-Rückmeldung** — N-CREATE/N-SET annehmen, Schritt speichern, Status als HL7 an das RIS zurückmelden (MLLP oder Webhook), API + UI + Tests | ✅ **erledigt** |
| 2 | **Feldweiser Merge + Mapping-Vorlagen** — je DICOM-Feld die Quelle bestimmen; HL7→DICOM-Mapping sichtbar und änderbar | ✅ **erledigt** |
| 3 | **DICOM Conformance Statement + IHE-Aussage** — Dokumente plus ein Test, der Dokument und Code zusammenhält | ✅ **erledigt** |
| 4 | **Statistik/Reporting** — Kennzahlen je Quelle/Modalität/Station und Tagesreihe, API + UI | ✅ **erledigt** |
| 5 | **UPS-RS** — DICOMweb-Worklist (Suche, Abruf, Anlegen, Statuswechsel) auf derselben Aggregation | ✅ **erledigt (Subset)** |

### Sprint 1 — MPPS SCP und Status-Rückmeldung (✅ erledigt)

Der Broker nimmt MPPS an (N-CREATE „IN PROGRESS", N-SET „COMPLETED"/
„DISCONTINUED"), speichert den Schritt mit Zeitstempeln und Schritt-ID und kann
den Status als **HL7-Nachricht an das RIS zurückschicken** (`ORU^R01` mit
Z01/Z02/Z03-Status, MLLP oder REST-Webhook, Zustellung im Hintergrund — der
DICOM-Pfad blockiert nie). Erfolgreiche Schritte verschwinden aus der eigenen
Arbeitsliste, fehlgeschlagene Rückmeldungen werden gezählt und sind über die API
erneut auslösbar.

**Nachweis:** `tests/test_mpps.py` (11 Tests: Parser, Anlegen/Ändern, N-SET ohne
N-CREATE, MLLP-Nachricht, Zustellung an einen **echten** MLLP-Empfänger,
Fehlerpfad ohne RIS, Sammel-Retry, echte DICOM-Assoziation mit N-CREATE/N-SET,
Ablehnung bei ausgeschaltetem MPPS, API-Endpunkte, „fertige Schritte kommen
nicht zurück"), `MppsCard.test.tsx` (4), verify-ui (2 Checks), Migration
`0008_mpps`, Retention-Tabelle `mpps_step`, Metriken
`mwl_mpps_steps_total`/`mwl_mpps_forwarded_total`.

### Sprint 2 — Feldweiser Merge und Mapping-Vorlagen (✅ erledigt)

Merge-Regeln legen **je DICOM-Feld** fest, aus welcher Quelle der Wert kommt
(Reihenfolge = Priorität); ohne Regel gilt weiter „erste Quelle gewinnt". Ein
Mapping-Editor macht die Zuordnung HL7 → DICOM-Worklist-Felder sichtbar und
änderbar.

**Nachweis:** `tests/test_merge_rules.py` (8: Standard-Merge unverändert, Feld aus
anderer Quelle, Reihenfolge, inaktive Regel, Felder in der SPS-Sequenz, API +
Validierung, Vorschau zeigt die Änderung), `tests/test_hl7_mapping.py` (7: ohne
Zuordnung unverändert, Füllen, Trockenlauf, Wert landet am Eintrag **und in der
C-FIND-Antwort**, inaktive Zuordnung, fehlendes Feld, Validierung),
`MergeRulesCard.test.tsx` (6), `Hl7MappingCard.test.tsx` (6), Migrationen
`0009_merge_rules`/`0010_hl7_field_map`/`0011_local_extra`.

### Sprint 3 — Conformance Statement und IHE-Aussage (✅ erledigt)

`docs/dicom-conformance-statement.md` (SOP-Klassen, Rollen, Transfer-Syntaxen,
Zeichensätze, Ports, Timeouts, Grenzen, TLS) und `docs/ihe-profile-statement.md`
(SWF/PIR-Bezug, abgedeckt vs. nicht abgedeckt). Ein Test prüft das Dokument
gegen den Code (SOP-Klassen aus `dimse.py`, AETs und Ports aus den Settings).

**Nachweis:** `tests/test_conformance_docs.py` (9 Tests: SOP-Klassen, Transfer-
Syntaxen inkl. Keyword, Storage-Anzahl, AET/Ports/Grenzwerte gegen die Settings,
Spool-Verhalten, „nicht unterstützt"-Liste gegen die Handler, MPPS-Schalter,
IHE-Profile). Der Test hat sofort zwei echte Abweichungen gefunden (Anzahl der
Storage-Klassen 117 → 120, Transfer-Syntaxen ohne Keyword).

### Sprint 4 — Statistik und Reporting (✅ erledigt)

`GET /api/v1/stats/overview` liefert Kennzahlen je Quelle, Modalität und Station
(Abfragen, Antworten, Bilder, Fehler, Spool, Dead Letters, mittlere Dauer) für
einen Zeitraum, plus eine Tagesreihe; die Oberfläche zeigt Balken und Tabelle.

**Nachweis:** `tests/test_stats.py` (8: Summen, Aufschlüsselung nach Quelle/
Modalität/Station, lückenfreie Tagesreihe, Zeitraumwahl und Grenzen, Spool-
Zustand, **PHI-Freiheit** — Patientennamen und Zugangsnummern tauchen nicht auf,
leerer Zeitraum), `StatsCard.test.tsx` (4).

### Sprint 5 — UPS-RS (DICOMweb-Worklist) (✅ erledigt, bewusst als Subset)

`/dicom-web/workitems` mit **Suche**, **Abruf**, **Anlegen** und
**Statuswechsel** — gemappt auf dieselbe Aggregation wie der DIMSE-Pfad.
Subscriptions/WebSocket-Ereignisse bleiben bewusst außen vor und werden im
Statement als Grenze genannt.

**Nachweis:** `tests/test_ups_rs.py` (7: Anlegen/Abruf/Suche, erneutes Anlegen
aktualisiert statt zu duplizieren, Statuswechsel nimmt den Eintrag aus der
Arbeitsliste (geprüft über die echte Aggregation), Status in beiden
Schreibweisen, Klartext-Validierung, per HL7-Mapping gefüllte Zusatzfelder
erscheinen im Work Item, stabile UID).

**Grenzen (im Conformance Statement dokumentiert):** keine Subscriptions/
WebSocket-Ereignisse, kein vollständiger UPS-Attributsatz, Suche nur über die
lokalen Work Items (Upstream-Quellen werden weiterhin per C-FIND mit dem
Identifier der Modalität abgefragt).
