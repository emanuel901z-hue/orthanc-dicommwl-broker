# IHE-Profil-Aussage — MWL Broker

Stand: 22.09.2026 · gehört zum [DICOM Conformance Statement](dicom-conformance-statement.md)

Diese Aussage ordnet den Broker in die IHE-Radiologie-Profile ein: was er
abdeckt, was er bewusst nicht abdeckt und welche Rolle er in einem
IHE-konformen Netz spielt. Grundlage für Ausschreibungen und für die Abnahme
mit RIS-/PACS-Herstellern.

## 1. Rolle im Netz

Der Broker sitzt **zwischen** den Modalitäten und den Auftraggebern (RIS/KIS).
Für die Modalität ist er der **Department System Scheduler / Order Filler** der
Worklist; für die RIS-/KIS-Systeme ist er ein **Client** (C-FIND) bzw. ein
**Sender** von Statusmeldungen (HL7).

```text
RIS A ─┐                        ┌─→ PACS Haus (C-STORE)
RIS B ─┼─→ [ MWL Broker ] ──────┤
KIS   ─┘   MWL SCP + MPPS SCP   └─→ PACS Partner (C-STORE)
             │      ↑
             │      └── Modalitäten: C-FIND (Worklist), C-STORE (Bilder), MPPS (Status)
             └───────── HL7 ORU (Status zurück an das RIS), ATNA (Audit)
```

## 2. Profil-Abdeckung

| IHE-Profil / Transaktion | Abdeckung | Anmerkung |
|---|---|---|
| **Scheduled Workflow (SWF)** — „Modality Worklist Provided" (DICOM MWL C-FIND) | **ja** | Kernfunktion: Aggregation mehrerer Auftraggeber, Merge, Dedupe, Stationsregeln |
| **SWF** — „Modality Performed Procedure Step" (MPPS, N-CREATE/N-SET) | **ja** | seit Sprint 1; Rückmeldung als HL7 `ORU^R01` (Z01/Z02/Z03) |
| **SWF** — „Procedure Scheduled / Updated" (HL7 `ORM^O01`) | **ja** | REST und MLLP; auch `CA` (Stornierung) |
| **Patient Information Reconciliation (PIR)** | **teilweise** | Identifier werden übernommen und je Fall zusammengeführt (Dedupe über PatientID+Accession+SPS); ein **MRN-Merge** (mehrere Patient-IDs derselben Person) ist **nicht** implementiert |
| **Consistent Presentation of Images / Evidence Documents** | **nein** | Der Broker ist kein Archiv/Viewer |
| **Retrieve Information for Display / XDS-I** | **nein** | keine Dokumenten-/Bildabfrage |
| **ATNA** (Audit Trail and Node Authentication) | **teilweise** | Audit-Nachrichten (RFC 3881/DICOM) können an eine Audit-Gegenstelle gesendet werden (`atna_enabled`); **Node Authentication** ist über DICOM-TLS mit Client-Zertifikaten möglich (`tls_inbound_client_auth`), ein Zertifikat-zu-AET-Mapping ist nicht implementiert |
| **PDQ / PIX** (Patient Demographics/Identifier Query) | **nein** | Patientendaten kommen aus den Auftragsnachrichten bzw. der lokalen Worklist |

## 3. Transaktions-Details (Scheduled Workflow)

| Transaktion | Auslöser | Antwort des Brokers |
|---|---|---|
| **Query Modality Worklist** (C-FIND) | Modalität fragt an | zusammengeführte Arbeitsliste aller Quellen (siehe Conformance Statement §4) |
| **Procedure Scheduled** (HL7 `ORM^O01` mit `NW`) | RIS/KIS sendet Auftrag | lokaler Eintrag wird angelegt/aktualisiert |
| **Procedure Updated** (`ORC-1 = XO/SC`) | RIS/KIS ändert den Auftrag | lokaler Eintrag wird aktualisiert |
| **Procedure Cancelled** (`ORC-1 = CA`) | RIS/KIS storniert | Eintrag wird entfernt/ungültig |
| **Performed Procedure Step Started** (MPPS N-CREATE) | Modalität beginnt | Schritt `IN PROGRESS` gespeichert |
| **Performed Procedure Step Completed/Discontinued** (MPPS N-SET) | Modalität beendet | Schritt `COMPLETED`/`DISCONTINUED`, HL7-Rückmeldung an das RIS, Ausblenden aus der Worklist |
| **Audit Record** (ATNA) | jede Abfrage/jeder Store | Audit-Nachricht an die Audit-Gegenstelle (optional) |

## 4. Was das Profil typischerweise verlangt — und wie es hier erfüllt ist

| Anforderung (SWF) | Umsetzung |
|---|---|
| Worklist muss aktuell sein | Live-Fan-out je Abfrage, Cache nur als Ausfallbrücke mit hartem Stale-Fenster (120 s) |
| Auftragsänderungen müssen ankommen | HL7-Intake (REST/MLLP) schreibt in die lokale Worklist, die mit höchster Priorität in die Antwort gemischt wird |
| Erledigte Schritte dürfen nicht erneut erscheinen | MPPS-Filter (`mpps_hide_completed`) **und** Verwerfen erledigter Schritte aus dem Cache |
| Der Auftraggeber muss den Status erfahren | HL7-Rückmeldung je MPPS-Übergang, mit Wiederholung und Fehlerzähler |
| Fehler dürfen die Modalität nicht blockieren | Timeout je Quelle, parallele Abfrage, Circuit Breaker, Antwort auch bei Totalausfall |
| Nachvollziehbarkeit | Änderungsprotokoll (Konfiguration), Query-/Store-Log (PHI-frei), ATNA-Export |

## 5. Bewusste Grenzen (im Statement dokumentiert)

Nicht Teil dieses Brokers: MRN-Merge/PIX-PDQ, Retrieve (C-MOVE/C-GET), Storage
Commitment, Prefetch von Voraufnahmen, Transkodierung, De-Identifikation,
UPS/UPS-RS (geplant), Zertifikat-zu-AET-Mapping im ATNA-Sinn.

Diese Punkte sind im [Conformance Statement §9](dicom-conformance-statement.md)
mit Begründung aufgeführt — sie sind Aufgabe von PACS, VNA oder eines Routers,
nicht eines Worklist-Brokers.
