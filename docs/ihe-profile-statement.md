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

RIS/KIS ──→ /oe3/IHEInvokeImageDisplay?requestType=STUDY&studyUID=…  (IID, RAD-106)
                 └─→ OE3 löst auf und öffnet den Viewer (OHIF, WADO-RS am Orthanc)
```

Der Viewer wird nicht über eine herstellerspezifische URL geöffnet, sondern über
den **IHE-IID-Einstiegspunkt** — dieselbe Adresse, die ein fremdes RIS/KIS
aufrufen würde. Damit ist der Weg, den wir selbst benutzen, auch der Weg, den
wir zusagen.

## 2. Profil-Abdeckung

| IHE-Profil / Transaktion | Abdeckung | Anmerkung |
|---|---|---|
| **Scheduled Workflow (SWF)** — „Modality Worklist Provided" (DICOM MWL C-FIND) | **ja** | Kernfunktion: Aggregation mehrerer Auftraggeber, Merge, Dedupe, Stationsregeln |
| **SWF** — „Modality Performed Procedure Step" (MPPS, N-CREATE/N-SET) | **ja** | seit Sprint 1; Rückmeldung als HL7 `ORU^R01` (Z01/Z02/Z03) |
| **SWF** — „Procedure Scheduled / Updated" (HL7 `ORM^O01`) | **ja** | REST und MLLP; auch `CA` (Stornierung) |
| **Patient Information Reconciliation (PIR)** | **ja** | Identifier werden übernommen, je Fall zusammengeführt (Dedupe über PatientID+Accession+SPS) und **zusammengeführt**: `ADT^A40` oder manuell eintragen; Arbeitsliste **und** Routing-Herkunft folgen der aktuellen ID, rücknehmbar. Ebenso `ADT^A24` (**Verknüpfung** — beide IDs bleiben gültig, es wird nichts umgeschrieben) und `ADT^A47` (Verknüpfung zurücknehmen), dazu `ADT^A08` (Patientendaten aktualisieren). Nicht enthalten: PIX/PDQ-Abfragen |
| **Consistent Presentation of Images / Evidence Documents** | **nein** | Der Broker ist kein Archiv/Viewer |
| **Retrieve Information for Display / XDS-I** | **nein** | keine Dokumenten-/Bildabfrage |
| **ATNA** (Audit Trail and Node Authentication) | **teilweise** | Audit-Nachrichten (RFC 3881/DICOM) können an eine Audit-Gegenstelle gesendet werden (`atna_enabled`); **Node Authentication** ist über DICOM-TLS mit Client-Zertifikaten möglich (`tls_inbound_client_auth`), ein Zertifikat-zu-AET-Mapping ist nicht implementiert |
| **PDQ / PIX** (Patient Demographics/Identifier Query) | **nein** | Patientendaten kommen aus den Auftragsnachrichten bzw. der lokalen Worklist |
| **Unified Procedure Step (UPS/UPS-RS)** | **teilweise** | REST-Worklist (Suche/Abruf/Anlegen/Statuswechsel) für lokale Aufträge; Subscriptions/Events fehlen (siehe Conformance Statement §9a) |
| **Invoke Image Display (IID)** — „Invoke Image Display" (RAD-106) | **ja** (OE3) | Der Viewer wird über den IID-Einstiegspunkt aufgerufen: `/oe3/IHEInvokeImageDisplay?requestType=STUDY&studyUID=…` (oder `accessionNumber=…`) bzw. `?requestType=PATIENT&patientID=…`. Study- **und** Patient-basierte Anfrage, komma-separierte Listen, `mostRecentResults`, `viewerType`/`diagnosticQuality` werden angenommen; Accession Number und PatientID löst OE3 gegen das PACS auf |
| **MADO** (Manifest-based Access to DICOM Objects, v1.0.0 trial-use) | **kein Akteur** | Content-Access-Profil — der Broker ist Workflow-Broker. Einordnung und Berührungspunkte in §6 |

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

## 6. MADO (Manifest-based Access to DICOM Objects) — Einordnung

MADO (v1.0.0, **trial-use**, publiziert am 03.09.2026) beschreibt den Zugriff
auf DICOM-Objekte **anhand eines Manifests** einer Studie; Treiber ist die
EHDS-Verordnung. Das Manifest fasst eine Studie zusammen — als DICOM KOS oder
als FHIR-`Bundle` vom Typ `document` (Composition, ImagingStudy, Patient,
Creator, RequestedProcedure, `Endpoint`-Ressourcen) — und wird über eine
Dokumenteninfrastruktur (MHD/XDS) verteilt. Die Bilder holt der Consumer
anschließend per **WADO-RS (RAD-107)** über die im Manifest genannten Endpunkte.

**Der Broker ist kein MADO-Akteur.** MADO ist ein Content-Access-Profil, der
Broker ist ein Workflow-Broker (SWF). Eine Konformitätsaussage „MADO" wäre
falsch, deshalb steht sie hier als Nicht-Rolle **mit** Begründung:

| MADO-Akteur | Wer in diesem Stack | Stand |
|---|---|---|
| Imaging Manifest Creator | PACS/VNA — nicht Teil des Stacks | **nein** — Manifest-Erzeugung (KOS/FHIR-Bundle, `Endpoint`-Ressourcen, MHD-`DocumentReference`) ist Archiv-/VNA-Aufgabe, siehe [Conformance Statement §9](dicom-conformance-statement.md) |
| Imaging Manifest Consumer | OHIF / OE3 | **nein** — der Viewer liest DICOMweb direkt, nicht über ein Manifest |
| WADO-RS-Responder (RAD-107) | mitgelieferter Orthanc | **ja** (`DicomWeb.EnableWado`) — aber ohne Manifest-Bezug |

### 6.1 Was der Broker trotzdem beiträgt

MADO bindet das Manifest über **Accession Number und Requested Procedure** an
den Auftrag zurück. Genau diese Korrelation besitzt der Broker: er hat die
Arbeitsliste beantwortet, den MPPS-Schritt angenommen und die Bilder geroutet.

`GET /api/v1/orders/context?study_uid=…` (oder `?accession=…`) liefert je
Auftrag Accession, SPS-ID, Station, Modalität, Verfahren, Termin, die
Arbeitslisten-Herkunft (welche Quelle kennt den Fall), den MPPS-Zustand und die
Zahl der bereits weitergeleiteten Instanzen. Ein Manifest Creator kann sein
Manifest damit an den Auftrag binden, statt die Beziehung zu raten. Der Aufruf
ist PHI-frei: der Patientenname verlässt den Broker nie, `PatientID` bleibt der
Korrelationsschlüssel.

### 6.2 Was für eine echte MADO-Aussage fehlt

Manifest-Erzeugung (KOS **oder** FHIR-Bundle), Ablage in einer
Dokumenteninfrastruktur (MHD/XDS) und ein Consumer, der das Manifest liest.
Alle drei fehlen in diesem Stack — und ohne konkrete Kundenanforderung sind sie
auch nicht geplant. Die EHDS-Frist für die Sekundärnutzung (2029) ist in
[`next-steps.md`](next-steps.md) als Beobachtungsposten vermerkt.

**Was diese Aussage wert ist:** Der Broker behauptet MADO nicht, nennt aber die
Berührungspunkte und die Lücke — damit eine Ausschreibung nicht an einer
fehlenden Zeile scheitert und ein späterer Ausbau nicht an einer falschen
Annahme.
