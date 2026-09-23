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

### Orthanc-Worklists: versucht, nicht brauchbar (für diesen Zweck)

Der naheliegende Kandidat für eine **zweite, unabhängige** MWL-Quelle war
Orthancs `orthanc-worklists`-Plugin (C++, anderes Projekt). Es ist im Test nicht
als speisbarer MWL-**SCP** verwendbar:

- Die REST-API (`PUT /worklists/{id}` mit `{"Tags": …}`) legt Einträge an — sie
  landen aber **nicht** in der konfigurierten Ordner-Ablage (`Worklists.Database`
  blieb leer), und der DICOM-Pfad liefert sie nicht aus.
- Ein direkt in den Ordner gelegtes Worklist-File wurde ebenfalls nicht
  ausgeliefert; nach einem Neustart war auch die REST-Sicht leer.
- Der DICOM-Pfad verlangt außerdem, dass die **calling AET** in
  `DicomModalities` steht (`This AET is not listed in DicomModalities`) — das ist
  ein *echter* Interop-Unterschied zu DCMTK's `wlmscpfs` (das jeden annimmt) und
  im Test berücksichtigt (`DicomAlwaysAllowFindWorklist`), aber die Ablage-Frage
  bleibt.

**Konsequenz:** Als fremder MWL-SCP bleibt DCMTK (`wlmscpfs`) — eine *zweite*
unabhängige Implementierung gibt es erst mit dem Gazelle Order Manager oder einem
echten RIS.

## 4. Was es sonst noch gibt — und warum es für uns ausfällt

| Werkzeug | Was es kann | Urteil |
|---|---|---|
| **DVTk** (DICOM Validation Toolkit, Windows/.NET) | **RIS-Emulator** (MWL **und** MPPS als SCP), Skript-Steuerung, und **DVT validiert gegen die eigene Conformance-Erklärung** („Definition Files") | **nicht installiert** auf der erreichbaren Windows-Workstation (per SSH geprüft) — die Fähigkeit „validiert unser Conformance Statement" hat sonst niemand; Installation dort wäre der nächste Schritt |
| **dcm4chee-arc-light** | vollständiges Archiv mit MWL-SCP, MPPS-SCP, DICOMweb, UI | zu schwer für unseren Zweck (wir wollen Werkzeuge, kein zweites PACS) |
| **Mirth Connect / NextGen Connect** (`nextgenhealthcare/connect`) | HL7-Integrations-Engine, Kanäle per REST/UI | eine Alternative zu `hl7snd`/`hl7rcv` — aber viel Konfiguration für dasselbe Ergebnis |
| **HAPI TestPanel** | HL7 senden/empfangen mit GUI | nicht skriptbar, Java-GUI |
| **Orthanc Worklists-Plugin** | **fremder MWL-SCP** (C++, im Stack vorhanden, standardmäßig aus) | **sofort nutzbar** als *zweite* unabhängige MWL-Implementierung — eine Zeile Konfiguration |
| **pynetdicom, pydicom, hl7apy** | Bibliotheken | wie DCMTK-Bibliotheken: fremder *Code*, aber unser Testcode — kein Ersatz für ein fremdes Produkt |
| **echte Modalität / echtes RIS** | der eigentliche Nachweis | nur auf einem Connectathon/Projectathon oder im Haus |

### Was die erreichbare Windows-Workstation bietet (per SSH geprüft)

| Gefunden | Bedeutung |
|---|---|
| `D:\Projekte`, `D:\VMs`, `D:\WSL`, Hyper-V/VirtualBox | eine vollwertige Windows-Testmaschine — DVTk liesse sich dort installieren |
| `C:\Program Files\Carestream\PACS\{hstpacs, ruepacs}`, `C:\Program Files\Philips\PACS\hstpacs` | **Hersteller-PACS-Clients** (zwei Standorte) |
| `medavisAgentService`, `medavisTsUsbService`, `DicomPacsWatcher` | Dienste eines deutschen RIS-Herstellers (medavis) und ein DICOM-Watcher |
| `C:\Program Files\sendscu\SendSCU.exe` (+ `sendscu.cfg`, binär) | ein **Hersteller-C-STORE-SCU** — als fremde Modalität einsetzbar |
| **DVTk ist installiert** | `C:\Program Files (x86)\DVTk` **und** fertige Arbeitsordner im Projektverzeichnis (`D:\Projekte\orthanc-dicommwl-broker\DVTk{risemu,storagescu,storagescp,qrscpemu,dvt,dicomnetworkanalyzer}`) — mein erster Suchlauf hatte nur `C:\Program Files` geprüft, das war falsch |
| **kein** lauschender DICOM-Port (104/2762/4242/11112) | die PACS-Server laufen dort nicht; es sind Clients/Viewer |

#### Versuch, dort tatsächlich zu testen — und was genau fehlt

Die Maschine wurde per SSH benutzt (der Nutzer ist lokaler Administrator). Der
Netzweg steht: `Test-NetConnection 10.0.1.47 -Port 11113` **→ True**, unser
Broker ist von dort erreichbar. Die Werkzeuge fehlen — und zwar aus konkreten
Gründen:

| Vorhaben | Befund | Was es bräuchte |
|---|---|---|
| **DVTk installieren** | **erledigt** — DVTk liegt auf der Maschine (Arbeitsordner unter `D:\Projekte\orthanc-dicommwl-broker\DVTk*`): RIS-Emulator, Storage SCU/SCP, Q/R-SCP-Emulator, `DVTCmd`, DICOM Network Analyzer, DICOM Compare. (Der Weg über die dvtk.org-Registrierung war nur nötig, solange ich `C:\Program Files` durchsucht hatte — die Tools lagen in `Program Files (x86)` und in den Projektordnern.) | nichts |
| **DVTk aus dem Quellcode bauen** | geklont ✓ (`C:\Users\Manu\dvtk-src`), MSBuild (VS Build Tools 18) ✓, .NET-4.8-Developer-Pack installiert ✓ — aber: die **DVT**-Solution enthält ein **`.vcproj`** (C++-Projekt, „DVTk Managed Code Adapter"), das modernes MSBuild ablehnt, und der **Modality Emulator** zielt auf **.NET Framework 4.0** (Targeting Pack fehlt) | Visual Studio mit C++-Workload auf der Maschine — dafür ist der Installer-Weg der kürzere |
| **Emulatoren fahren** | Die Emulatoren **mit** Oberfläche (RIS, Storage SCU/SCP, Q/R) müssen **gestartet** werden — danach sind sie über den SSH-Tunnel erreichbar (der RIS-Emulator lief so, mit dir am Gerät). Der **Storage-SCP ist zusätzlich ohne Oberfläche** fahrbar: `DVTCmd -estscp` + `dvtk_emulator.py` (hält stdin offen) | einmal starten (Klick), dann läuft es |
| **DVT zur Validierung** | `DVT Command Line` (Konsole, `DVTCmd.exe`) existiert, hängt aber an derselben Solution; die DICOM-`.def`-Dateien liegen im Repo ✓, die **2024a-Standard-Definition-Files sind kommerziell** | Build + ggf. die kommerziellen Definition Files |
| **`SendSCU.exe` als fremde Modalität** | Delphi-**GUI**-App, Konfiguration **binär** (`sendscu.cfg`, nicht patchbar); die Logs zeigen `Sent H:\FILES\…` — **`H:` existiert nicht mehr** (nur C, D) | Neu-Konfiguration über die Oberfläche am Gerät |
| **Carestream-/Philips-Client als Gegenprobe** | nur `DicomXMLBrowser.exe` (Viewer) — **kein** CLI-DICOM-Werkzeug in den Herstellerordnern | ein laufender Fremd-Server (Lizenz) oder ein Hersteller-Testtool |

**Fazit:** Der Vendor-Test **läuft** — über `DVTCmd.exe`, die Konsolenvariante von
DVT, die per SSH fahrbar ist und jede empfangene Nachricht gegen die
DICOM-Definition-Dateien validiert (XML-Berichte). **Fünf Szenarien PASSED**
(C-ECHO, MWL C-FIND, C-STORE eingehend, MPPS, C-STORE ausgehend); dazu der
RIS-Emulator als fremde MWL-Quelle. Ergebnisse stehen in
[`interop.md`](interop.md) §2b und in `deploy/interop/dvtk/README.md`; die
Skripte liegen in `deploy/interop/dvtk/`.

Was einen Menschen braucht: die Emulatoren **mit Oberfläche** müssen einmal
**gestartet** werden (danach erreichbar), und **`SendSCU`** (binäre
Konfiguration, `H:` existiert nicht mehr). Für die Validierung gegen *unser*
Conformance Statement bräuchte DVT zusätzlich eine eigene Definition-Datei
unseres Systems — **das** ist der offene Punkt, nicht die Emulatoren.

Der Netzweg ist bewiesen: **jedes** Fremdwerkzeug auf dieser Maschine erreicht
den Broker unter `10.0.1.47:11113`.

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
| 1 | ~~**`OMI^O23` + `ADT^A31` unterstützen**~~ — **erledigt** | die modernen Varianten der Auftrags- bzw. Patientennachricht; jetzt gegen die fremden Beispielnachrichten geprüft | — |
| 2 | ~~**Orthanc-Worklists als zweite fremde MWL-Quelle**~~ — **versucht, nicht brauchbar** (siehe unten) | — | — |
| 3 | **Gazelle-Zugang** (HL7-Validator, Order Manager, Security Suite) | Kodierungsprüfung durch Fremdsoftware, fremde SWF-Gegenseite, fremde TLS-Peers | organisatorisch |
| 4 | ~~**DCMTK-TLS**~~ — **erledigt**: `storescp +tls` (mTLS) und `echoscu +tla`/`storescu +tla` in `deploy/interop-test.sh` | unser TLS/mTLS gegen einen fremden TLS-Stack, beide Richtungen | — |
| 5 | **DVTk auf einer Windows-Workstation** | validiert gegen unser Conformance Statement — sonst kann das niemand | organisatorisch |
| 6 | **Connectathon/Projectathon** | echte Geräte, echte RIS — der eigentliche E1-Nachweis | Termin |

Was **nicht** auf die Liste gehört: das Gazelle-Test-Bed lokal aufsetzen, das
`framework`-Repo, dcm4chee-arc als zweites PACS, Mirth als HL7-Engine. Alle vier
kosten mehr, als sie für unsere Frage bringen.
