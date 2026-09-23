# Externe Kompatibilitätsprüfung (E1)

Stand: 22.09.2026 · Ergebnis von **E1** aus [`next-steps.md`](next-steps.md)

Bisher war **jede** DIMSE-Gegenstelle unser eigener Code: `mock-ris-a/b` und
`dicom-peer` bauen aus `./mwl-broker`, die DIMSE-Tests nutzen
`mwl_broker.mock_ris`. Das Conformance Statement war damit an unseren Code
gebunden — aber nie gegen fremde Software belegt. Dieses Dokument beschreibt, was
davon inzwischen belegt ist, womit — und was weiterhin fehlt.

## 1. Teil 1: DICOM gegen DCMTK (belegt)

**DCMTK** (OFFIS) ist eine der verbreitetsten DICOM-Implementierungen
(Jahrzehnte in Kliniken, Teil von Debian/Ubuntu). Auf dem Prüfhost genügt
`sudo apt install dcmtk` — dann steht echte Fremdsoftware als Gegenüber bereit:

| DCMTK-Werkzeug | Rolle | wogegen geprüft |
|---|---|---|
| `wlmscpfs` | **fremdes RIS** (Modality Worklist SCP), gespeist aus DCMTKs Beispiel-Worklist (10 Einträge) | unser **SCU**: der Broker holt die Arbeitsliste aus fremder Software |
| `findscu -W` | **fremde Modalität** (MWL C-FIND SCU) | unser **SCP**: was die Modalität sieht — Antwortaufbau, Encoding |
| `storescu` | **fremde Modalität** (C-STORE SCU) | unser **SCP** + Routing bis in ein fremdes PACS |
| `dcmqrscp` | **fremdes PACS** (C-STORE SCP) | unser **SCU**: Store-Routing zu fremder Software |
| `echoscu` | fremde Modalität (C-ECHO) | unser SCP, in beide Richtungen |
| `dcmdump` | **fremder Decoder** | was tatsächlich angekommen ist — nicht von pydicom gelesen |

**Zweiter Fremdstack: dcm4che** (`dcm4che/dcm4che-tools:5.33.1`) — für das, was
DCMTK nicht hat (MPPS, HL7):

| dcm4che-Werkzeug | Rolle | wogegen geprüft |
|---|---|---|
| `mppsscu` | **fremde Modalität mit MPPS** (N-CREATE/N-SET) | unser MPPS-SCP — vorher gab es dafür **kein** Werkzeug |
| `hl7snd` | fremder **HL7-Sender** (MLLP) mit echten IHE-MESA-Beispielnachrichten | unser MLLP-Listener (Auftrag angenommen, Befund abgelehnt) |
| `hl7rcv` | fremder **HL7-Empfänger** | unsere MPPS-Statusmeldung — angenommen und abgelegt |

```bash
./deploy/interop-test.sh          # aufbauen, prüfen, abbauen (~2 min)
./deploy/interop-test.sh --keep   # Stack + Fremdsoftware stehen lassen
```

**Dritter Fremdstack: DCMTK-TLS** (`storescp +tls`, `echoscu +tla`, `storescu +tla`) —
TLS in beide Richtungen, inklusive **mTLS** (DCMTK's Server verlangt ein
Client-Zertifikat: „peer did not return a certificate").

**Und ein methodischer Fund, der die Aussagekraft betraf:** `~/.local/bin`
enthält **Python-Wrapper** mit denselben Namen wie die DCMTK-Werkzeuge
(`findscu`, `storescu`, `echoscu`, `storescp` — es sind pynetdicom-CLI-Apps) und
liegt **vor** `/usr/bin` im PATH. Ein Test, der `findscu` aufruft, prüft dann
unsere *eigene* Bibliothek statt Fremdsoftware. Das Skript nutzt jetzt absolute
Pfade und weist nach, dass die Werkzeuge wirklich DCMTK sind.

Ergebnis (Referenzlauf): **23 von 23 Prüfungen bestanden** — der Broker liest
die fremde Worklist (10 Einträge), die fremde Modalität bekommt genau diese 10
Einträge zurück (mit DCMTKs Beispieldaten: `VIVALDI^ANTONIO`,
`HAYDN^FRANZ` …), ein von der fremden Modalität geschicktes Bild wird über die
Regel in das **fremde PACS** geroutet und dort von `dcmdump` als
`AccessionNumber 00003` gelesen.

## 2. Was diese Tests gefunden haben

**Sieben** Fehler, jeder für unsere eigenen Tests unsichtbar, weil unser Mock die
Auslöser nie erzeugt:

1. **Mehrwertige Attribute.** DCMTKs Worklist trägt `ScheduledStationAETitle`
   mit **mehreren** Stationen je Schritt — legal und in echten RIS-Antworten
   verbreitet. Das landete in einer Metadatenspalte (`varchar(16)`), Postgres
   lehnte ab (`value too long for character varying(16)`) — und weil der
   Cache-Schreibvorgang im selben `try` wie die Abfrage stand, war die **ganze
   Antwort verloren** und die funktionierende Quelle wurde als Fehler gezählt.
2. **Ein Cache-Fehler kostete die Antwort.** Der Cache ist die
   *Ausfallbrücke*, die RIS-Antwort ist das, was die Modalität braucht. Ein
   Schreibfehler darf die Antwort nicht mitnehmen — und schon gar nicht den
   Circuit Breaker einer gesunden Quelle öffnen.

3. **MPPS ohne `AffectedSOPInstanceUID`.** DICOM erlaubt der Modalität, die UID
   dem SCP zu überlassen (PS3.7) — dcm4che's `mppsscu` macht genau das, und
   unser Handler antwortete „Cannot understand" (0xC000): **der
   Untersuchungsschritt erreichte das RIS nie.** Jetzt vergibt der SCP die UID
   und liefert sie in der Antwort zurück (pynetdicom nimmt sie aus dem
   Rückgabe-Dataset), sodass das folgende N-SET den Schritt trifft.
4. **Unser ACK war um zwei Felder verschoben** (Zeitstempel in MSH-6, „ACK" in
   MSH-8, Control-ID in MSH-9) — ein strenges RIS liest das als „keine
   Bestätigung für meine Nachricht" und sendet erneut. Ein ACK **tauscht** die
   Adressfelder; jetzt tut er das.
5. **MSH-6 (Receiving Facility) fehlte** in der MPPS-Statusmeldung — der fremde
   Empfänger antwortete `MSA|AE|… Missing Receiving Facility`. Neues Setting
   `mpps_forward_facility` (Default `RIS`).
6. **MSH-9 wurde komplett verglichen.** Echte Nachrichten tragen den dritten
   Bestandteil — die Nachrichtenstruktur (`OMG^O19^OMG_O19`); ein gültiger
   fremder Auftrag wurde deshalb abgelehnt. `hl7.message_code` vergleicht nur
   `code^trigger`.
7. **Der Schalter `hl7_mllp_enabled` war wirkungslos**: die Oberfläche zeigt ihn,
   der Start entschied über den Env-Wert. Ein Schalter, der nichts tut, ist
   schlimmer als keiner.

Behoben in `upstream.meta_text` (erster Wert, auf Spaltenbreite begrenzt — der
Payload behält alles), angewendet in `cache._describe` und
`dimse._record_seen_items`; Isolation des Cache-Schreibvorgangs in `aggregation`;
SCP-vergebene MPPS-UID; ACK-Adresstausch; `mpps_forward_facility`;
`hl7.message_code`; Start liest die Einstellung. Regressionstests:
`tests/test_interop_findings.py` (6), `tests/test_mpps.py`,
`tests/test_hl7.py`, `tests/test_hl7_types.py`.

**Und eine offene Konformitätslücke:** `OMI^O23` (Imaging Order — die *moderne*
Radiologie-Auftragsnachricht, in den fremden Beispieldaten enthalten) und
`ADT^A31` (Update Person Information) lehnt der Broker ab. Siehe
[`interop-tools.md`](interop-tools.md) §5.

**Und zwei Konformitätslücken sind geschlossen:** `OMI^O23` (Imaging Order — die
*moderne* Radiologie-Auftragsnachricht, in den fremden Beispieldaten enthalten)
und `ADT^A31` (Update Person Information, Variante von A08) werden jetzt
angenommen — beides direkt gegen die fremden Nachrichten geprüft.

## 2b. DVTk auf einer Windows-Workstation (Teil 3, läuft)

**DVTk** (DICOM Validation Toolkit, Philips/ICT Group) ist das Werkzeug, auf dem
auch die IHE-RO-Validierung aufsetzt. Auf einer erreichbaren Windows-Maschine ist
es installiert; die Konsolenvariante **`DVTCmd.exe`** ist per SSH fahrbar und
validiert jede empfangene Nachricht gegen die **DICOM-Definition-Dateien** — eine
Prüfung, die unsere eigenen Tests nicht leisten können. Die Skripte liegen in
[`../deploy/interop/dvtk/`](../deploy/interop/dvtk/README.md).

| Szenario | Ergebnis |
|---|---|
| **C-ECHO** (DVTk-Beispiel) | **PASSED** — 0 Validierungsfehler |
| **Modality Worklist `C-FIND`** | **PASSED** — 0 Validierungsfehler (Skript aus einer echten Antwort erzeugt, s. u.) |
| **C-STORE** (DVTk erzeugt ein Secondary-Capture-Bild im Skript) | **PASSED**; der Store liegt nachweislich im Broker (`/logs/stores`: `DVTK_SCU … success`) |
| **MPPS** `N-CREATE` + `N-SET` (eigenes Skript mit gültiger UID) | **PASSED** — 0 Validierungsfehler |
| **Ausgehender C-STORE** (unser Broker → DVTk als PACS) | **PASSED** — 0 Validierungsfehler; DVTk legte die empfangenen Objekte als Media ab |

Damit ist die **komplette SWF-Kette** — Arbeitsliste, Bildannahme,
Schrittmeldung, Lebenszeichen — von einem fremden, herstellergeprägten Werkzeug
gegen die DICOM-Definition-Dateien geprüft.

**Zwei Dinge, die dafür nötig waren** (beide im Generator dokumentiert):
DVTks Skriptmodus vergleicht die *Werte*, und unser Arbeitslisten-Answer enthält
Werte, die nur der laufende Stack kennt (der Mock-RIS erzeugt seine Study
Instance UIDs beim Start, das Untersuchungsdatum ist „heute + Versatz") — das
Skript wird deshalb aus einer echten C-FIND-Antwort **erzeugt**
(`deploy/interop/dvtk/generate_mwl_script.py`). Und der Antwortblock muss auch
die **Kommando-Elemente** deklarieren (`(0000,0002)` Affected SOP Class UID),
sonst meldet DVTk sie als „not present in reference object".

**Zwei Befunde aus diesem Lauf:**

1. **DVTks eigenes MPPS-Beispiel ist fehlerhaft.** Es sendet und erwartet die
   SOP-Instanz-UID `"MppsUID"` — keine gültige DICOM-UID. DVTks *eigener*
   Validator beanstandet genau das (`Attribute (0000,1000) value should start
   with digit(s)`). Unser Broker hat korrekt geantwortet (DIMSE verlangt, die
   angeforderte UID zurückzugeben); mit einer echten UID läuft dasselbe Szenario
   fehlerfrei durch.
2. **Unser MPPS-SCP ist bewusst nachsichtig:** ein `N-SET` ohne vorheriges
   `N-CREATE` wird angenommen und der Schritt gespeichert, statt mit `0x0112`
   (No Such SOP Instance) zu antworten. DICOM erlaubt die Ablehnung — DVTks
   Beispiel macht aber genau diesen Fall, und die Nachsicht rettet die
   Information für das RIS. Steht so im Conformance Statement.

## 3. Was das **nicht** belegt

- **Keine HL7-*Validierung*:** dcm4che prüft den Nachrichtenaufbau so weit, dass
  es gültige von ungültigen Nachrichten trennt (es hat unsere fehlende MSH-6
  erkannt) — eine Profilvalidierung gegen den IHE-Anwendungsfall macht nur der
  Gazelle HL7 Validator (§4).
- **Kein echtes Gerät, kein echtes RIS:** DCMTK und dcm4che sind Fremdsoftware,
  aber keine Modalitäten-Hersteller mit ihren Eigenheiten. Der Connectathon
  bleibt das Ziel.
- **Kein TLS mit fremden *Zertifikaten* aus einer echten PKI:** der Handshake und
  mTLS sind gegen DCMTK geprüft, aber mit selbst erzeugten Zertifikaten (Gazelle
  Security Suite würde eine echte Test-PKI liefern).
- **Keine Dauerlast** (dafür gibt es [`loadtest.md`](loadtest.md)).
- **Keine Validierung gegen *unsere* Conformance-Erklärung:** DVTk prüft gegen
  den DICOM-Standard; für „System gegen eigene Definition-Datei" bräuchte es
  eine solche Datei (und die kommerziellen 2024a-Definition-Files).

## 4. Teil 2: Gazelle (vorbereitet, nicht durchgeführt)

### Was Gazelle ist — und was nicht

Gazelle ist das Test-Bed der IHE-Connectathons: **Test-Management,
Validierung, Simulation**. Es ist *nicht* die Gegenseite für unseren
Workflow — aber es hat die passenden Bausteine:

| Gazelle-Werkzeug | Für uns relevant als | Nutzen |
|---|---|---|
| **Gazelle HL7 Validator** | Validierung unserer Nachrichten (HL7v2.x im IHE-Kontext) | unabhängige Aussage zur **Kodierung** — die Lücke aus §3 |
| **Order Manager** (Simulator) | fremder Auftraggeber/-nehmer für **Radiology Scheduled Workflow** | eine *fremde* SWF-Gegenseite, die Aufträge platziert/abholt |
| **Patient Manager** (Simulator) | fremder Patient-Index für **PDQ** | die Gegenseite für F2c (PIX/PDQ), falls gebaut |
| Test Management | Connectathon-/Projectathon-Sitzungen | der organisatorische Weg zu echten Geräten |

Nicht sinnvoll: das **`framework`-Repo** (Java-Bibliothek, um eigene
Gazelle-Tools zu *bauen*) und ein **lokaler Aufbau des ganzen Test-Beds**
(SSO, Test Management, Proxy, EVSClient … auf Debian stretch, Java 7/8, Tomcat 8,
JBoss 7, Wildfly 10, PostgreSQL 9.6 — alles EOL). Zugang zu den Werkzeugen läuft
über die öffentlichen/Connectathon-Instanzen
(<https://connectathon.ihe-catalyst.net/gazelle/home>), also über eine
Registrierung.

### Der konkrete nächste Schritt (15 Minuten, ohne Account)

Die Beispielnachrichten liegen bereit: `deploy/interop/samples/` (ORM, OMG, ADT
A08/A24/A40/A47, plus eine `ORU^R01` als **Negativbeispiel**). Ablauf:

1. Beim Connectathon-/Projectathon-Zugang anmelden (IHE-Konto) oder die
   Nachrichten an einen Partner mit Zugang geben.
2. Im **Gazelle HL7 Validator** hochladen und gegen den passenden
   IHE-Anwendungsfall validieren lassen.
3. Den Prüfbericht hier ablegen (`docs/`-Anhang oder Ticket) — mit Datum,
   Validator-Version und Ergebnis.

Erwartung: die Auftrags- und Patienten-Ereignisse sind gültiges HL7 v2.5 für
ihren Anwendungsfall; die `ORU^R01` ist gültiges HL7, aber kein Auftrag — genau
das, was unser Broker ablehnt (siehe §2 der [IHE-Aussage](ihe-profile-statement.md)).

### Und danach: der Connectathon

Der eigentliche E1-Nachweis ist ein **Projectathon** mit dem Order Manager als
Gegenüber (SWF) — dort treffen wir auf fremde Implementierungen *und* auf die
Feinheiten, die kein Simulator nachbildet. Aufwand: Vorbereitung klein (Testfälle
existieren), Durchführung ein Termin.

## 5. Was sich durch diesen Teil an den Aussagen ändert

- Das [Conformance Statement](dicom-conformance-statement.md) nennt in §10
  jetzt, wogegen geprüft wurde (DCMTK) und was weiterhin fehlt.
- Die [IHE-Aussage](ihe-profile-statement.md) führt E1 als *teilweise belegt*:
  DICOM-Seite mit Fremdsoftware, HL7-Seite und echte Geräte offen.
