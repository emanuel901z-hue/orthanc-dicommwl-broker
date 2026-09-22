# DICOM Conformance Statement — MWL Broker

Software: `mwl-broker` (dieser Repository-Stand), Version siehe
`mwl-broker/pyproject.toml` · Bibliothek: pynetdicom 3.0.4 / pydicom
Stand: 22.09.2026

Dieses Dokument beschreibt, welche DICOM-Dienste der Broker anbietet und nutzt.
Es ist die Grundlage für jede Ausschreibung und für die Abnahme mit den
Modalitäten-Herstellern. Die Angaben sind **aus dem Code geprüft** —
`tests/test_conformance_docs.py` hält Dokument und Implementierung zusammen.

## 1. Rollen im Überblick

| Dienst | Rolle | Wann |
|---|---|---|
| Modality Worklist C-FIND | **SCP** (Server) | immer — die Modalitäten fragen hier |
| Verification (C-ECHO) | **SCP** | immer |
| Storage (C-STORE) | **SCP** | immer — Bilder für das Store-Routing |
| Modality Performed Procedure Step (MPPS) | **SCP** (N-CREATE, N-SET) | wenn `mpps_enabled` (Standard: an) |
| Modality Worklist C-FIND | **SCU** (Client) | zu jeder konfigurierten Upstream-Quelle |
| Verification (C-ECHO) | **SCU** | Überwachung der Quellen/Ziele, „C-ECHO jetzt" |
| Storage (C-STORE) | **SCU** | Weiterleitung an die konfigurierten PACS-Ziele |

Der Broker ist **kein** Archiv: er speichert keine Bilder dauerhaft (nur den
Sendepuffer bis zur Zustellung).

## 2. Application Entities und Netzwerk

| Parameter | Wert (Standard) | Einstellung |
|---|---|---|
| AET des Brokers | `MWLBROKER` | `BROKER_AET` / `broker_aet` |
| Port (Klartext) | `11113` | `BROKER_DICOM_PORT` / `dicom_port` |
| Port (TLS, optional) | `2762` | `tls_inbound_port`, nur bei `tls_inbound_enabled` |
| Maximale Assoziationen | `20` | `max_associations` |
| Antwort-AET (SCU) | konfigurierbar je Quelle (`calling_aet`) | Quelle/Ziel |
| Erlaubte Calling-AETs | leer = alle | `allowed_calling_aets` (empfohlen: einschränken) |

Der Broker bietet **keinen** „Requested Application Entity"-Filter an: die
Prüfung erfolgt über die **Calling**-AET (`allowed_calling_aets`). Ist die Liste
leer, wird jede Calling-AET akzeptiert (Werkseinstellung, im Health-Panel als
Hinweis gemeldet).

**Hochverfügbarkeit ändert diesen Abschnitt nicht.** Auch mit zwei Instanzen
gibt es **einen** AET und **einen** Port, den die Modalitäten ansprechen; welche
Instanz dahinter antwortet, entscheidet die Netzwerkebene (schwebende IP,
TCP-Load-Balancer) — siehe [`ha.md`](ha.md). Beide Instanzen sind funktional
identisch, teilen Konfiguration und Datenbank und stellen Spool-Einträge genau
einmal zu (Claim + Lease); die Zustellsemantik ist **at-least-once**, nicht
exactly-once.

**Oberhalb von `max_associations` wird abgewiesen, nicht gepuffert** — das ist
gemessen (siehe [`loadtest.md`](loadtest.md) §3.2): bei mehr gleichzeitigen
Verbindungen als dem Limit antwortet der Broker mit einer
Assoziations-Ablehnung, die Modalität muss wiederholen. Die Zahl der
*gleichzeitig* verbundenen Konsolen ist damit die Dimensionierungsgröße, nicht
die Zahl der konfigurierten Geräte.

Transport: TCP/IP v4. TLS optional und pro Richtung getrennt (siehe §6).

## 3. Presentation Contexts

Angeboten (SCP) werden die Transfer-Syntaxen, die pynetdicom für die
registrierten Kontexte vorschlägt:

| Transfer Syntax | UID | Keyword (pynetdicom) |
|---|---|---|
| Implicit VR Little Endian | 1.2.840.10008.1.2 | `ImplicitVRLittleEndian` |
| Explicit VR Little Endian | 1.2.840.10008.1.2.1 | `ExplicitVRLittleEndian` |
| Explicit VR Big Endian | 1.2.840.10008.1.2.2 | `ExplicitVRBigEndian` |
| Deflated Explicit VR Little Endian | 1.2.840.10008.1.2.1.99 | `DeflatedExplicitVRLittleEndian` |

Angefragt (SCU) wird **Implicit VR Little Endian** für C-FIND und C-ECHO; für
C-STORE wird die Transfer-Syntax des empfangenen Objekts beibehalten (keine
Transkodierung — der Broker ändert keine Pixel).

### SOP-Klassen

| Dienst | SOP-Klasse | UID |
|---|---|---|
| MWL C-FIND (SCP/SCU) | Modality Worklist Information Model – FIND | 1.2.840.10008.5.1.4.31 |
| Verification (SCP/SCU) | Verification SOP Class | 1.2.840.10008.1.1 |
| Storage (SCP/SCU) | Storage Service Class — **120** SOP-Klassen | siehe Anhang A |
| MPPS (SCP, N-CREATE/N-SET) | Modality Performed Procedure Step | 1.2.840.10008.3.1.2.3.3 |

**Anhang A — Storage-SOP-Klassen:** Der Broker akzeptiert alle Storage-Klassen,
die pynetdicom auflistet (120 Klassen: CT, MR, US, CR/DX, NM, PT, XA, SR, PR,
SEG, RT-*, Waveforms, Secondary Capture, Encapsulated PDF/CDA, …). Eine
vollständige Liste liefert
`python3 -c "from pynetdicom import StoragePresentationContexts; print(sorted({c.abstract_syntax.name for c in StoragePresentationContexts}))"`.

## 4. C-FIND (Modality Worklist) — Verhalten

**Anfrage (SCP):** Der Broker nimmt den Identifier an und wertet die üblichen
Matching-Schlüssel aus (AccessionNumber, PatientID, StudyInstanceUID,
Modality, ScheduledStationAETitle, SPS-Datum/-Zeit, RequestedProcedureID,
ScheduledProcedureStepID). Nicht unterstützte Schlüssel werden ignoriert
(kein Fehler).

**Antwortaufbau:** Fan-out an alle aktiven Quellen (parallel, Timeout je Quelle
`upstream_timeout_s`, Standard 10 s) → Merge nach Priorität → Dedupe über
`(PatientID, AccessionNumber, ScheduledProcedureStepID)` → Feldregeln
(`merge_rules`) → Stationsregeln (Prioritäts-Override und Sichtbarkeitsfilter)
→ Ausblenden fertiger MPPS-Schritte.

**Status-Codes:** `0xFF00` je Antwort, `0x0000` am Ende, `0xA700` bei nicht
erlaubter Calling-AET, `0xC000` bei unverständlicher Anfrage.

**Verhalten bei Störungen:** Eine tote Quelle verzögert die Antwort nicht
(Timeout je Quelle, parallele Abfrage). Ein offener Circuit Breaker
(`breaker_fail_threshold` = 3 Fehler, `breaker_open_seconds` = 60 s) überspringt
die Quelle ganz. Ist ein Cache-Snapshot vorhanden (`cache_enabled`), wird er
geliefert (max. `cache_stale_max_s` = 120 s nach der letzten erfolgreichen
Abfrage) und der Eintrag im Protokoll als „stale" markiert.

**Antwortumfang:** Der Broker streamt Antworten (kein vollständiger Puffer im
Speicher), begrenzt aber den Cache je Quelle auf `cache_max_items` = 5000
Einträge.

## 5. C-STORE (Store-Routing) — Verhalten

Eingehende Objekte werden anhand der Worklist-Herkunft geroutet
(`seen_items`: Accession → Quelle → Regel → Ziel). Ohne Treffer gilt das
Standardziel; ohne Standardziel wird das Objekt **abgewiesen** (kein stilles
Verwerfen). Optional werden Modify-Regeln (Tag-Änderungen) angewendet.

Kann ein Ziel nicht erreicht werden, wird das Objekt gepuffert
(`spool_enabled`, Standard an): maximal `spool_max_items` = 20 000 Objekte bzw.
`spool_max_bytes` = 10 GiB, danach **Abweisung** (nie stilles Verwerfen),
`spool_max_attempts` = 10 Versuche mit exponentiellem Backoff
(`spool_backoff_s` = 60 s Basis). Bei `strict_store_status` (Standard an) wird
der Zustellfehler der Modalität als DIMSE-Fehler gemeldet; bei
`accept_when_queued` (Standard an) gilt ein sicher gepuffertes Objekt als
angenommen.

## 6. Sicherheit (TLS, mTLS)

| Richtung | Einstellungen | Standard |
|---|---|---|
| Eingehend (Modalitäten → Broker) | `tls_inbound_enabled`, `tls_inbound_port`, Zertifikat/Schlüssel/CA, `tls_inbound_client_auth` (`none`/`optional`/`required`) | **aus** (Klartext-Port bleibt parallel nutzbar) |
| Ausgehend (Broker → RIS/PACS) | je Knoten `tls`, `tls_verify`, global `tls_outbound_ca_file`, optionales Client-Zertifikat | `tls` aus, `tls_verify` an |

Die Zertifikatsprüfung erfolgt über den Server-Namen (hostname checking); ein
Abschalten von `tls_verify` wird im Health-Panel als Warnung geführt. Private
Schlüssel werden nie über die API ausgegeben und mit Modus 0600 abgelegt.

## 7. Zeichensätze

Je Quelle konfigurierbar (`charset`, Standard `ISO_IR 100` = Latin-1). Der Broker
setzt `SpecificCharacterSet` in den Antworten und übernimmt den Zeichensatz der
Quelle; UTF-8 (`ISO_IR 192`) wird unterstützt, wenn die Quelle ihn verwendet.

## 8. MPPS (Modality Performed Procedure Step)

Angeboten, wenn `mpps_enabled` (Standard an):

* **N-CREATE** → Schritt mit Status `IN PROGRESS`, Speicherung der Identifier
  (Accession, PatientID, SPS-ID, Station, Modalität, Study-UID) und Zeitstempel.
* **N-SET** → `COMPLETED` oder `DISCONTINUED`.
* **N-GET** wird unterstützt: die Modalität kann den gespeicherten Schritt
  zurücklesen (Status, Accession, SPS-ID, Station, Modalität, Zeiten) — manche
  Geräte prüfen das vor dem Weiterarbeiten.
* **N-ACTION** wird **nicht** unterstützt (kein MPPS-Manager; der Broker
  schließt Aufträge nicht selbst).
* Rückmeldung an das RIS: HL7 `ORU^R01` (Z01/Z02/Z03) über MLLP
  (`mpps_forward_port`, Standard 2575) oder HTTP-Webhook, asynchron, mit
  Wiederholungsmöglichkeit über die API.
* Fertige Schritte verschwinden aus der Worklist (`mpps_hide_completed`).

## 9. Nicht unterstützt (bewusste Grenzen)

| Dienst | Status | Begründung |
|---|---|---|
| UPS / UPS-RS (Unified Procedure Step, DICOMweb) | **teilweise** | REST-Worklist unter `/api/v1/dicom-web/workitems` (Suche, Abruf, Anlegen, Statuswechsel) — **ohne** Subscriptions/WebSocket-Ereignisse und ohne den vollständigen UPS-Attributsatz; die Suche umfasst die lokalen Work Items |
| C-MOVE / C-GET (Query/Retrieve) | nicht | Der Broker verteilt Bilder per C-STORE, nicht per Retrieve |
| Storage Commitment (N-ACTION) | nicht | Aufgabe des Archivs/PACS |
| Basic Study Content Notification | nicht | Aufgabe des PACS |
| N-EVENT-REPORT / N-ACTION allgemein | nicht | keine Empfänger-Rolle implementiert |
| General Purpose Worklist | nicht | 2011 zurückgezogen |
| Print Management | nicht | kein Druckdienst |
| Transkodierung / Pixel-Manipulation | nicht | Der Broker ändert keine Bilddaten |
| De-Identifikation (PS3.15) | nicht | gehört in einen Router mit Pseudonym-Verwaltung |
| Prefetch von Voraufnahmen | nicht | Aufgabe von PACS/VNA |
| Manifest-basierter Zugriff (IHE MADO) | nicht | Content-Access-Profil (Manifest + WADO-RS) — Aufgabe von PACS/VNA/Viewer. Der Broker liefert nur die Auftragskorrelation, siehe §9c und [IHE-Aussage §6](ihe-profile-statement.md) |

## 9a. UPS-RS (DICOMweb-Worklist)

Der Broker bietet einen **pragmatischen Teil** von PS3.18 §11 an:

| Transaktion | Pfad | Anmerkung |
|---|---|---|
| Search | `GET /api/v1/dicom-web/workitems?AccessionNumber=…` | DICOM-JSON-Antwort; Suchschlüssel: AccessionNumber, PatientID, PatientName, ScheduledStationAETitle, Modality, ScheduledProcedureStepStartDate, ScheduledProcedureStepID, StudyInstanceUID, ProcedureStepState |
| Retrieve | `GET /api/v1/dicom-web/workitems/{uid}` | UID stabil je Work Item |
| Create | `POST /api/v1/dicom-web/workitems` | legt einen lokalen Auftrag an (AccessionNumber Pflicht) |
| Change state | `PUT /api/v1/dicom-web/workitems/{uid}/state` | SCHEDULED, IN PROGRESS, COMPLETED, CANCELED; COMPLETED/CANCELED nehmen den Eintrag aus der Arbeitsliste |

**Nicht enthalten:** Subscriptions und Ereignisberichte (WebSocket), der
vollständige UPS-Attributsatz, Suche über Upstream-Quellen (die werden weiterhin
per C-FIND mit dem Identifier der Modalität abgefragt).

## 9b. Patient identifier reconciliation (IHE PIR)

Der Broker führt Patienten-IDs zusammen — der Fall „Notfallaufnahme, später
zusammengeführt" oder „zwei Systeme, zwei MRN":

| Ereignis | Bedeutung | Wirkung im Broker |
|---|---|---|
| `ADT^A40` | **Zusammenführen** — die alte ID entfällt | wird gespeichert und angewandt: lokale Einträge und Routing-Herkunft ziehen um, die C-FIND-Antwort trägt die aktuelle ID |
| `ADT^A24` | **Verknüpfen** — beide IDs bleiben gültig | wird gespeichert; `resolve` folgt der Verknüpfung, aber **nichts wird umgeschrieben** und keine Daten ziehen um |
| `ADT^A47` | Verknüpfung zurücknehmen | deaktiviert die Verknüpfung; eine Zusammenführung wird **nie** durch ein A47 aufgehoben |
| `ADT^A08` | Patientendaten aktualisiert | schreibt die Demografie der **eigenen** Arbeitslisten-Einträge um (nur die Felder, die die Nachricht trägt); eine zusammengeführte ID wird vorher aufgelöst |

| Weg | Aufruf |
|---|---|
| Über REST | `POST /api/v1/hl7/adt` (mit `dry_run=true` zuerst) |
| Über MLLP | derselbe Parser auf dem MLLP-Port (`hl7_mllp_port`) — ein RIS sendet ADT dort, wo es auch die Aufträge sendet |
| Manuell | `POST /api/v1/merges` mit `kind=merge` (Default) oder `kind=link` |
| Rücknehmen | `DELETE /api/v1/merges/{id}` — außer Kraft, Eintrag bleibt für das Änderungsprotokoll |
| Prüfen | `GET /api/v1/merges/resolve/{id}` — folgt der Kette (A→B→C), zyklensicher |

Ein `A40` **nach** einem `A24` für dasselbe Paar stuft die Verknüpfung zur
Zusammenführung hoch — sonst bliebe die alte ID für immer stehen.

**Nicht enthalten:** PIX-/PDQ-Abfragen, die automatische Auflösung aus dem PACS
und das Umschreiben zwischengespeicherter Snapshots (der Cache ist eine
Upstream-Kopie mit kurzem Stale-Fenster; siehe `adt.py`).

## 9c. Auftragskontext (REST, für MADO-Manifest-Erzeuger)

`GET /api/v1/orders/context?study_uid=…` (oder `?accession=…`) beantwortet „zu
welchem Auftrag gehört diese Studie?" — Accession, SPS-ID, Station, Modality,
Verfahren, Termin, Arbeitslisten-Herkunft, MPPS-Zustand und die Zahl der bereits
weitergeleiteten Instanzen. Quellen sind die lokale Worklist, die
Worklist-Herkunft (`seen_items`), die MPPS-Schritte und das Store-Log. Der
Aufruf ist PHI-frei: der Patientenname wird nie zurückgegeben, `PatientID` ist
der Korrelationsschlüssel.

Dies ist **kein** MADO-Manifest und macht den Broker zu keinem MADO-Akteur — es
ist die Auftragskorrelation, die ein Manifest-Erzeuger braucht
([IHE-Aussage §6](ihe-profile-statement.md)).

## 10. Grenzen und Betriebswerte

| Größe | Wert | Einstellung |
|---|---|---|
| Antwort-Timeout je Quelle | 10 s | `upstream_timeout_s` |
| C-ECHO-Intervall (Überwachung) | 30 s | `echo_interval_s` |
| Circuit Breaker | 3 Fehler / 60 s | `breaker_fail_threshold`, `breaker_open_seconds` |
| Cache je Quelle | 5000 Einträge, 120 s stale | `cache_max_items`, `cache_stale_max_s` |
| Spool | 20 000 Objekte / 10 GiB / 10 Versuche | `spool_max_items`, `spool_max_bytes`, `spool_max_attempts` |
| Assoziationen | 20 gleichzeitig | `max_associations` |
| HL7 MLLP (eingehend) | 2575 | `hl7_mllp_port` |
| ATNA (Syslog/TLS) | 6514 | `atna_syslog_port` |

## 10a. Wogegen geprüft wurde (externe Kompatibilität)

Die Aussagen dieses Dokuments sind durch Tests an den Code gebunden. Darüber
hinaus wurde die DICOM-Seite gegen **Fremdsoftware** geprüft — DCMTK (OFFIS),
eine der verbreitetsten DICOM-Implementierungen:

| Fremdsoftware | Rolle | Ergebnis |
|---|---|---|
| `wlmscpfs` | fremdes RIS (MWL SCP) | unser SCU liest dessen Worklist (10 Einträge) |
| `findscu -W` | fremde Modalität | unser SCP liefert genau diese 10 Einträge, von DCMTK dekodiert |
| `storescu` | fremde Modalität | C-STORE angenommen und regelbasiert geroutet |
| `dcmqrscp` | fremdes PACS | das Bild kommt dort an (`dcmdump`: `AccessionNumber 00003`) |
| `echoscu` | fremde Modalität | C-ECHO in beide Richtungen |
| `mppsscu` (dcm4che) | **fremde Modalität mit MPPS** | unser MPPS-SCP nimmt N-CREATE/N-SET an — inklusive des Falls, dass die Modalität die SOP-Instanz-UID dem SCP überlässt |
| `hl7snd` (dcm4che) | fremder HL7-Sender | unser MLLP-Listener: Auftrag angenommen, Befund abgelehnt |
| `hl7rcv` (dcm4che) | fremder HL7-Empfänger | unsere MPPS-Statusmeldung (ORU^R01) wird angenommen |
| `storescp +tls` (DCMTK) | fremder TLS-Server, verlangt ein Client-Zertifikat | unser **mTLS-Client** liefert ein Bild dorthin (mTLS in beide Richtungen) |
| `echoscu +tla`, `storescu +tla` (DCMTK) | fremder TLS-Client | unser TLS-Listener: C-ECHO und C-STORE über TLS |

Nachweis: `./deploy/interop-test.sh` (**23 Prüfungen**, DCMTK + dcm4che) und
[`interop.md`](interop.md). **Noch nicht** geprüft: eine HL7-*Profilvalidierung*
durch den Gazelle HL7 Validator (Beispiele liegen in `deploy/interop/samples/`),
TLS mit Zertifikaten aus einer echten PKI und der Einsatz an einem echten Gerät
bzw. RIS (Connectathon). Die dabei gefundenen Fehler stehen in
[`interop.md`](interop.md) §2.

**Angenommene Nachrichtentypen** (jeweils gegen fremde Beispiele geprüft):
`ORM^O01`, `OMG^O19`, `OMI^O23` (Imaging Order) als Aufträge; `ADT^A08` und
`ADT^A31` (Update Person Information) als Patientendaten-Aktualisierung, dazu
`A24`/`A40`/`A47`. Alles andere wird abgelehnt — mit Begründung.

## 11. Konformität zu den IHE-Profilen

Siehe [`ihe-profile-statement.md`](ihe-profile-statement.md).
