# Werkzeuge für die externe Kompatibilitätsprüfung

Stand: 22.09.2026 · Recherche zu **E1** („welche Tools fehlen uns noch, um fremde
Software und fremde Hardware sauber zu evaluieren")

[`interop.md`](interop.md) beschreibt, *was* geprüft ist. Dieses Dokument
beschreibt, **womit** — und was noch fehlt. Es ist das Ergebnis einer Durchsicht
des Gazelle-Test-Beds (Core, Tools, Ecosystem) und des weiteren Umfelds.

## 1. Was wir schon haben

| Werkzeug | Rolle | Stand |
|---|---|---|
| **DCMTK** (`wlmscpfs`, `dcmqrscp`, `findscu`, `storescu`, `echoscu`, `dcmdump`) | fremdes RIS, fremdes PACS, fremde Modalität, fremder Decoder | im Einsatz (`deploy/interop-test.sh`, 10 Prüfungen) |
| **dcm4che** (`mppsscu`, `hl7snd`, `hl7rcv`) | fremde **Modalität mit MPPS**, fremder **HL7-Sender und -Empfänger** | im Einsatz (5 Prüfungen) |
| **Orthanc** | fremdes PACS (C-STORE-Ziel) + DICOMweb | im Stack |
| eigene Mocks (`mock-ris`, `dicom-peer`) | Entwicklung, **kein** Interop-Nachweis | bewusst so benannt |

## 2. Gazelle — was das Test-Bed hergibt

Gazelle ist das Test-Bed der IHE-Connectathons. Es ist **Test-Management,
Validierung und Simulation**, nicht die Gegenseite für unseren Workflow.

| Gazelle-Teil | Was es ist | Für uns |
|---|---|---|
| **Gazelle HL7 Validator** | validiert HL7v2/v3 im IHE-Kontext | **offen, wertvoll**: die HL7-Seite ist bisher nur von unserem Parser geprüft. Beispiele liegen bereit (`deploy/interop/samples/`) |
| **Order Manager** (Simulator) | fremder Auftraggeber/-nehmer, u. a. **Radiology Scheduled Workflow** | **offen**: eine fremde SWF-Gegenseite — der beste Ersatz für „ein echtes RIS" ohne Connectathon |
| **Patient Manager** + **Demographic Data Server** | fremder Patient-Index, **PDQ/PIX** über v2/v3/FHIR | relevant, wenn **F2c** gebaut wird |
| **Gazelle Security Suite (GSS)** | Test-PKI, **TLS-Simulatoren** | **offen**: unser TLS/mTLS ist bisher mit pynetdicom auf beiden Seiten geprüft; GSS liefert fremde Zertifikate und einen fremden TLS-Peer |
| **Proxy** | „Man in the middle", zeichnet Nachrichten auf | nützlich als Beweismittel bei einem Event; lokal durch `tcpdump`/`dcm4che syslog` ersetzbar |
| **Test Management** | Registrierung, Testfälle, Testbericht | der organisatorische Weg zum Connectathon |
| **EVSClient** | Bedienoberfläche für alle Validatoren | der Zugang zu den Validatoren |
| Ecosystem: NIST XDS Toolkit/MHD, Matchbox, ITB, ART-DECOR | ITI, FHIR, CDA | **nicht unser Bereich** (kein XDS/CDA/FHIR-Akteur) |

**Zugang:** über die öffentlichen/Connectathon-Instanzen
(<https://connectathon.ihe-catalyst.net/gazelle/home>) — also mit IHE-Konto.
Ein **lokaler Aufbau des Test-Beds ist nicht sinnvoll**: die
Installationsanleitung (`ihe-gazelle-deployment`) baut SSO, Test Management,
Proxy, EVSClient, DDS, FHIR- und HL7-Validator auf Debian *stretch*, Tomcat 8,
JBoss 7, Wildfly 10, Java 7/8 und PostgreSQL 9.6 auf — EOL-Software für
Test-Management, das wir für ein einzelnes Produkt nicht brauchen. Das
`framework`-Repo ist eine Java-Bibliothek, um **eigene** Gazelle-Tools zu bauen —
die falsche Ebene.

## 3. dcm4che — der Fund, der zwei Lücken geschlossen hat

`dcm4che` (Java, Apache-2.0) liegt als Container bereit
(`dcm4che/dcm4che-tools:5.33.1`) und enthält Werkzeuge, die sonst **nirgends**
zu bekommen sind:

| Werkzeug | Rolle | Schließt unsere Lücke |
|---|---|---|
| **`mppsscu`** | fremder **MPPS-SCU** (N-CREATE/N-SET) | ✅ **MPPS gegen Fremdsoftware** — vorher gab es dafür kein Werkzeug |
| **`hl7snd`** | fremder **HL7-Sender** (MLLP) | ✅ HL7-Eingang gegen Fremdcode, mit echten Beispielnachrichten |
| **`hl7rcv`** | fremder **HL7-Empfänger** | ✅ unsere Statusmeldung, von fremder Software angenommen |
| `mppsscp` | MPPS-SCP **mit IOD-Validierung** (`--ncreate-iod`) | relevant, falls wir je MPPS-SCU werden |
| `modality` | Modalitäten-Emulator | Option für Dauer-/Lasttests |
| `hl7pdq`, `hl7pix` | PDQ-/PIX-Clients | die Gegenseite für **F2c** |
| `upsscu` | UPS-SCU | unsere UPS-RS-Teilmenge gegen fremden UPS |
| `ianscu`/`ianscp`, `stgcmtscu` | IAN, Storage Commitment | nur, wenn wir diese Rollen je anbieten |
| `dcmvalidate` | Validierung gegen IODs | unabhängige Objektprüfung |
| `syslog`, `syslogd` | ATNA-Sender/-Empfänger | unser ATNA-Export gegen einen fremden Empfänger |
| `qstar`, `wadors`, `stowrs` | DICOMweb-Clients | unser Orthanc-DICOMweb-Pfad gegen fremde Clients |
| `dcm2json`, `dcm2xml`, `dcmdump` | fremde Decoder | was wir tatsächlich senden |

**Und: echte fremde Beispieldaten.** Im Image liegen HL7-Nachrichten aus den
alten IHE-**MESA**-Testdaten (`/opt/dcm4che/etc/testdata/hl7/`): `OMG^O19`,
`OMI^O23`, `ADT^A31`, `ADT^A40`, `ADT^A47`, `ORU^R01`, `SIU^S12` — plus
DICOM-Beispiele. Genau diese Dateien haben zwei Konformitätslücken aufgedeckt
(§5).

## 4. Was es sonst noch gibt — und warum es für uns ausfällt

| Werkzeug | Was es kann | Urteil |
|---|---|---|
| **DVTk** (DICOM Validation Toolkit, Windows/.NET) | **RIS-Emulator** (MWL **und** MPPS als SCP), Skript-Steuerung, und **DVT validiert gegen die eigene Conformance-Erklärung** („Definition Files") | **interessant, aber Windows-only** — auf diesem Linux-Host nicht lauffähig. Die Fähigkeit „validiert unser Conformance Statement" hat sonst niemand: für eine Windows-Workstation vormerken |
| **dcm4chee-arc-light** | vollständiges Archiv mit MWL-SCP, MPPS-SCP, DICOMweb, UI | zu schwer für unseren Zweck (wir wollen Werkzeuge, kein zweites PACS) |
| **Mirth Connect / NextGen Connect** (`nextgenhealthcare/connect`) | HL7-Integrations-Engine, Kanäle per REST/UI | eine Alternative zu `hl7snd`/`hl7rcv` — aber viel Konfiguration für dasselbe Ergebnis |
| **HAPI TestPanel** | HL7 senden/empfangen mit GUI | nicht skriptbar, Java-GUI |
| **Orthanc Worklists-Plugin** | **fremder MWL-SCP** (C++, im Stack vorhanden, standardmäßig aus) | **sofort nutzbar** als *zweite* unabhängige MWL-Implementierung — eine Zeile Konfiguration |
| **pynetdicom, pydicom, hl7apy** | Bibliotheken | wie DCMTK-Bibliotheken: fremder *Code*, aber unser Testcode — kein Ersatz für ein fremdes Produkt |
| **echte Modalität / echtes RIS** | der eigentliche Nachweis | nur auf einem Connectathon/Projectathon oder im Haus |

## 5. Was die Werkzeuge gefunden haben

Sieben Fehler, die unsere eigenen Tests nicht sehen konnten — **keiner** davon war
durch Unit-Tests findbar, weil unser Mock die Auslöser nie erzeugt:

| # | Fund | Aufgedeckt von | Behoben |
|---|---|---|---|
| 1 | **Mehrwertige Attribute** (mehrere Stationen je Schritt) sprengten eine Metadatenspalte — die *ganze* Antwort war verloren und die gesunde Quelle wurde als Fehler gezählt | DCMTK (`wlmscpfs`) | `upstream.meta_text` |
| 2 | **Ein Cache-Schreibfehler kostete die Antwort** und öffnete den Breaker einer gesunden Quelle | DCMTK | eigener `try` in `aggregation.collect` |
| 3 | **MPPS ohne `AffectedSOPInstanceUID`** (DICOM erlaubt das — dann vergibt der SCP) wurde mit „Cannot understand" abgelehnt: der Untersuchungsschritt erreichte das RIS nie | dcm4che (`mppsscu`) | SCP vergibt und liefert die UID zurück |
| 4 | **Unser ACK war um zwei Felder verschoben** (Zeitstempel in MSH-6, „ACK" in MSH-8, Control-ID in MSH-9) — ein strenges RIS liest das als „keine Bestätigung" und sendet erneut | dcm4che (`hl7rcv`, strenger Empfänger) | Adresstausch (MSH-3/4 → MSH-5/6) |
| 5 | **MSH-6 fehlte** in der MPPS-Statusmeldung — der fremde Empfänger lehnte sie mit `MSA-1 = AE` ab („Missing Receiving Facility") | dcm4che (`hl7rcv`) | Setting `mpps_forward_facility` |
| 6 | **MSH-9 wurde komplett verglichen**: echte Nachrichten tragen den dritten Bestandteil (`OMG^O19^OMG_O19`) — ein gültiger fremder Auftrag wurde abgelehnt | dcm4che-Beispielnachrichten | `hl7.message_code` (nur `code^trigger`) |
| 7 | **Der Schalter `hl7_mllp_enabled` war wirkungslos**: die UI zeigt ihn, der Start entschied über den Env-Wert | beim Aufbau des Tests | Start liest die Einstellung |

**Noch offen (bewusst):** `OMI^O23` (Imaging Order — die *moderne*
Radiologie-Auftragsnachricht, in den dcm4che/MESA-Daten enthalten) und
`ADT^A31` (Update Person Information, Variante von A08) lehnt der Broker ab. Beide
haben dasselbe Segment-Layout wie die unterstützten Typen (`OMG`/`ORM` bzw.
`A08`) — kleine Erweiterungen, aber sie gehören entschieden, nicht nebenbei
gemacht.

## 6. Empfehlung

| Priorität | Was | Warum | Aufwand |
|---|---|---|---|
| 1 | **`OMI^O23` + `ADT^A31` unterstützen** | die modernen Varianten der Auftrags- bzw. Patientennachricht; fremde Daten zeigen sie, wir lehnen sie ab | klein |
| 2 | **Orthanc-Worklists als zweite fremde MWL-Quelle** in den Interop-Test | zweite unabhängige Implementierung, sofort verfügbar | klein |
| 3 | **Gazelle-Zugang** (HL7-Validator, Order Manager, Security Suite) | Kodierungsprüfung durch Fremdsoftware, fremde SWF-Gegenseite, fremde TLS-Peers | organisatorisch |
| 4 | **DCMTK-TLS** (`dcmqrscp --enable-tls`, `storescu +tls`) | unser TLS/mTLS gegen fremden TLS-Stack, lokal | klein–mittel |
| 5 | **DVTk auf einer Windows-Workstation** | validiert gegen unser Conformance Statement — sonst kann das niemand | organisatorisch |
| 6 | **Connectathon/Projectathon** | echte Geräte, echte RIS — der eigentliche E1-Nachweis | Termin |

Was **nicht** auf die Liste gehört: das Gazelle-Test-Bed lokal aufsetzen, das
`framework`-Repo, dcm4chee-arc als zweites PACS, Mirth als HL7-Engine. Alle vier
kosten mehr, als sie für unsere Frage bringen.
