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

```bash
./deploy/interop-test.sh          # aufbauen, prüfen, abbauen (~2 min)
./deploy/interop-test.sh --keep   # Stack + Fremdsoftware stehen lassen
```

Ergebnis (Referenzlauf): **10 von 10 Prüfungen bestanden** — der Broker liest
die fremde Worklist (10 Einträge), die fremde Modalität bekommt genau diese 10
Einträge zurück (mit DCMTKs Beispieldaten: `VIVALDI^ANTONIO`,
`HAYDN^FRANZ` …), ein von der fremden Modalität geschicktes Bild wird über die
Regel in das **fremde PACS** geroutet und dort von `dcmdump` als
`AccessionNumber 00003` gelesen.

## 2. Was dieser Test gefunden hat

Beide Fehler waren für unsere eigenen Tests unsichtbar, weil unser Mock sie nie
auslöst:

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

Behoben in `upstream.meta_text` (erster Wert, auf Spaltenbreite begrenzt — der
Payload behält alles), angewendet in `cache._describe` und
`dimse._record_seen_items`, plus Isolation des Cache-Schreibvorgangs in
`aggregation`. Regressionstests: `tests/test_interop_findings.py` (6).

## 3. Was das **nicht** belegt

- **Kein MPPS gegen fremde Software:** DCMTK bringt keinen MPPS-SCU. Die
  N-CREATE/N-SET-Seite bleibt mit pynetdicom als Client geprüft (fremde
  *Bibliothek*, aber unser Testcode).
- **Kein HL7-Gegenüber:** DCMTK ist DICOM. Die HL7-Seite (ORM/OMG/ADT eingehend,
  ACK/ORU ausgehend) ist damit **nicht** fremd geprüft — dafür §4.
- **Kein echtes Gerät, kein echtes RIS:** DCMTK ist Fremdsoftware, aber kein
  Modalitäten-Hersteller mit seinen Eigenheiten. Der Connectathon bleibt das Ziel.
- **Keine Dauerlast, kein TLS** in diesem Test (TLS ist separat geprüft,
  [`runbook.md`](runbook.md) §9).

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
