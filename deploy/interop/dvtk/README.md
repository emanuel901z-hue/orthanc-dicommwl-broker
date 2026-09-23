# DVTk-Skripte für die externe Validierung (E1, Teil 3)

**DVTk** (DICOM Validation Toolkit, Philips/ICT Group) ist das Werkzeug, auf dem
auch die IHE-RO-Validierung aufsetzt. Seine Konsolenvariante **`DVTCmd.exe`** ist
per SSH fahrbar und **validiert jede empfangene Nachricht gegen die
DICOM-Definition-Dateien** — eine Prüfung, die unsere eigenen Tests nicht leisten
können.

## Ergebnis (Referenzlauf, 23.09.2026)

| Szenario | Skript | Ergebnis |
|---|---|---|
| **C-ECHO** (DVTk-Beispiel) | `Verification_Scu/1.ds` | **PASSED** — 0 Validierungsfehler |
| **Modality Worklist C-FIND** | `mwl_live.ds` (erzeugt, s. u.) | **PASSED** — 0 Validierungsfehler |
| **C-STORE** (DVTk erzeugt ein Secondary-Capture-Bild im Skript) | `Storage_Scu/2.dss` | **PASSED**; der Store liegt nachweislich im Broker (`/logs/stores`: `DVTK_SCU … success`) |
| **MPPS** `N-CREATE` + `N-SET` | `mpps_interop.ds` | **PASSED** — 0 Validierungsfehler |
| **Ausgehender C-STORE** (Broker → DVTk als PACS) | Storage-SCP-Emulator (`dvtk_emulator.py`) | **PASSED** — 0 Validierungsfehler; DVTk legte die Objekte als Media ab (`1I00001.dcm`, `1I00002.dcm`) |

Damit ist die **komplette SWF-Kette** (Arbeitsliste, Bildannahme, Schrittmeldung,
Lebenszeichen) von einem fremden, herstellergeprägten Werkzeug gegen den
DICOM-Standard geprüft.

## Die Skripte

| Datei | Zweck |
|---|---|
| `mpps_interop.ds` | MPPS: `N-CREATE` (IN PROGRESS) + `N-SET` (COMPLETED) mit **gültiger** UID |
| `mwl_interop.ds` | MWL `C-FIND` mit *leeren* Referenzwerten — dokumentiert den Antwortaufbau, läuft aber nicht „grün" (s. u.) |
| `generate_mwl_script.py` | erzeugt aus einer **echten** C-FIND-Antwort des laufenden Brokers ein Skript mit den exakten Werten (`mwl_live.ds`) |
| `Storage_Scu/2.dss`, `Verification_Scu/1.ds` | unveränderte DVTk-Beispiele |

### Warum der Generator nötig ist

DVTks Skriptmodus **vergleicht die empfangenen Werte** mit denen im Skript. Unser
Arbeitslisten-Answer enthält Werte, die nur der laufende Stack kennt: der
Mock-RIS erzeugt seine Study Instance UIDs beim Start (`generate_uid()`), und das
Untersuchungsdatum ist „heute + Versatz". Ein von Hand geschriebenes Skript kann
deshalb nie passen — der Generator fragt den Broker per C-FIND und schreibt die
Antwort hinein:

```bash
python3 generate_mwl_script.py --host 127.0.0.1 --port 11113 > mwl_live.ds
scp mwl_live.ds <windows>:D:/Projekte/orthanc-dicommwl-broker/DVTk-interop/Query_Scu/
```

Nach einem Neustart des Stacks (oder am nächsten Tag) neu erzeugen.

## Wie man sie fährt

Auf der Windows-Maschine (Beispielpfade, der Broker läuft auf dem Linux-Host):

```powershell
cd D:\Projekte\orthanc-dicommwl-broker\DVTkdvt\Bin
.\DVTCmd.exe "D:\...\Verification_Scu\ECHO_SCU.ses" "D:\...\Verification_Scu\1.ds"
.\DVTCmd.exe "D:\...\Query_Scu\Query_SCU.ses"       "D:\...\Query_Scu\mwl_live.ds"
.\DVTCmd.exe "D:\...\Storage_Scu\Storage_SCU.ses"   "D:\...\Storage_Scu\2.dss"
.\DVTCmd.exe "D:\...\Mpps_Scu\MPPS_SCU.ses"         "D:\...\Mpps_Scu\mpps_interop.ds"
```

Die Beispiel-Sessions liegen im DVTk-Quellbaum
(`DVT/Resources/Example/Scripts/...`); `SUT-AE-TITLE`, `SUT-HOSTNAME` und
`SUT-PORT` müssen auf den Broker zeigen.

## Drei Befunde aus diesen Läufen

1. **DVTks eigenes MPPS-Beispiel ist fehlerhaft:** es sendet und erwartet die
   SOP-Instanz-UID `"MppsUID"` — keine gültige DICOM-UID. DVTks *eigener*
   Validator beanstandet das (`value should start with digit(s)`). Mit einer
   echten UID (`mpps_interop.ds`) läuft dasselbe Szenario fehlerfrei.
2. **Unser MPPS-SCP ist bewusst nachsichtig:** ein `N-SET` ohne vorheriges
   `N-CREATE` wird angenommen und der Schritt gespeichert, statt mit `0x0112`
   (No Such SOP Instance) zu antworten — dokumentiert im Conformance Statement
   §9d. DVTks Beispiel macht genau diesen Fall.
3. **Der Antwortaufbau muss vollständig deklariert werden:** DVTk meldet
   fehlende Attribute als „not present in reference object", auch die
   *Kommando*-Elemente (`(0000,0002)` Affected SOP Class UID). Und
   `RequestedProcedureID` (0040,1001) liefert der Broker auf **oberster Ebene**,
   nicht innerhalb der SPS-Sequenz — beides steht jetzt im Generator.

## Der Storage-SCP-Emulator (unsere *ausgehenden* C-STOREs)

`DVTCmd -estscp` macht DVTk zum **fremden PACS**: es nimmt unsere C-STOREs an und
validiert jeden gegen die Definition-Dateien. Der Weg dahin hatte vier Fallen:

1. **Emulator-Session, nicht Skript-Session.** Die Beispiele unter
   `DVT/Resources/Example/Scripts/...` sind `SESSION-TYPE script`; `-estscp`
   bricht damit ab („ScriptSession kann nicht in EmulatorSession umgewandelt
   werden"). Vorlage ist `DVT/Resources/Example/Emulators/Emulator_1/Emulator_1.ses`.
2. **`SUT-ROLE requestor`** (DVTk ist hier der SCP) und die Transfer-Syntax des
   Aufrufers in der Liste: unser Broker sendet Explicit VR Little Endian
   (`1.2.840.10008.1.2.1`) — fehlt sie, wird jede Assoziation abgelehnt.
3. **stdin muss offen bleiben** („Press ENTER to Stop") — dafür gibt es
   `dvtk_emulator.py` (Python `Popen` mit `stdin=PIPE`), das den Emulator startet,
   die Laufzeit begrenzt und ihn wieder beendet.
4. **Netzrichtung:** die Windows-Box blockt eingehende Verbindungen vom
   Linux-Host (Windows-Firewall ist aus, aber Sophos läuft; SSH auf 22 geht).
   Ohne deren Firewall anzufassen: eine **SSH-Portweiterleitung**
   (`ssh -N -L <host-ip>:<port>:127.0.0.1:<DVT-PORT> …`) — und dabei **127.0.0.1**
   statt `localhost` verwenden: auf Windows löst `localhost` zuerst auf `::1`
   auf, der Emulator lauscht aber nur auf IPv4 (`Socket closed during socket
   read`).

Damit lief es durch: der Broker lieferte zwei Bilder (aus dem Spool) an den
Emulator, DVTk validierte sie mit **0 Fehlern** und legte sie als Media ab.

## RIS-Emulator: getestet — und drei echte Fehler gefunden

Der **RIS Emulator** (`RIS Emulator.exe`) ist DVTks fremdes RIS: er bedient
**Modality Worklist C-FIND** und **MPPS N-CREATE/N-SET** als SCP. Er ist
**GUI-only** — `DVTCmd` kennt dafür keinen Modus —, also muss ihn jemand **am
Gerät** starten (Konsole/RDP): Reiter *Worklist* → Local AE `DVTK_MWL_SCP`,
Port, Remote AE `DVTK_MWL_SCU` (das ist unser Broker als Aufrufer) → *Start*.
Der Datenordner liegt unter
`%USERPROFILE%\Documents\DVTk\RIS Emulator\Data\Worklist\`; daraus baut er
sein Informationsmodell (Reiter *DICOM Files* → „View information model…").

**Netzweg:** die Box blockt eingehende Verbindungen vom Linux-Host, deshalb wie
beim Storage-SCP eine **SSH-Portweiterleitung** auf `127.0.0.1:<DVT-PORT>`
(nicht `localhost` — Windows löst das zuerst als `::1` auf). Danach ist das
fremde RIS für den Broker eine **Quelle** wie jede andere:

```text
Ziel: AET DVTK_MWL_SCP, Host <gateway>, Port <tunnel>, calling_aet DVTK_MWL_SCU
```

### Ergebnis

| Prüfung | Ergebnis |
|---|---|
| Fremde Arbeitsliste direkt gelesen | **6 Antworten** (Three^/Two^/One^Secondary Capture Image, `SC-I3/I2/I1`, `pidP645` + `AccessionNumber 00000187`) |
| Durch unseren Broker aggregiert (C-FIND einer Modalität) | **7 Einträge** — die 3 Mock-Patienten **plus** die 4 fremden (`SC-I3/I2/I1`, `pidP645`) |
| Cache der Quelle danach | **4 Einträge, available** (6 Antworten → 4 eindeutige Schlüssel) |

### Fund 1 (fremde Seite): `QueryRetrieveLevel` tötet die Antwort

Deterministisch gemessen (je 3 Läufe):

| Identifier der Anfrage | Antworten |
|---|---|
| `{PatientName, PatientID, AccessionNumber}` (leer) | **6, 6, 6** |
| `{SPS-Sequenz}` (leer) | **6, 6, 6** |
| `{SPS-Sequenz}` + `QueryRetrieveLevel = "MODALITY WORKLIST"` | **0, 0, 0** |

DVTk behandelt `(0008,0052)` als **Matching-Schlüssel**; seine Arbeitslisten-
einträge haben das Attribut nicht, also passt nichts. Nach DICOM gehört
`QueryRetrieveLevel` **nicht** zum Modality-Worklist-Informationsmodell, und ein
leerer Wert bedeutet *universelles* Matching (PS3.4, C.2.2.2). Wer das Attribut
sendet, ist Implementierungssache: ein **pynetdicom**-SCU tat es in der Messung,
**DCMTK's `findscu -W` nicht** (direkt gegen den Emulator: 6 Antworten). Eine
Modalität, die es sendet, bekommt von diesem Emulator eine **leere Arbeitsliste**
— durch unseren Broker gemessen: **3 Einträge** mit unverändert weitergegebenem
Identifier gegen **7** mit dem Schalter `strip_query_retrieve_level` (4 davon aus
dem fremden RIS). Unser Broker reicht den Identifier standardmäßig unverändert
weiter (genau richtig, sonst gingen Filter verloren).

### Fund 2 (unser Broker): doppelte Schlüssel sprengten den Cache-Upsert

DVTks Antwort enthält **drei Einträge mit demselben `dedupe_key`**
(`SC-I1||` — Patient gleich, Accession und Schritt-ID leer). Der Cache schreibt
seine Momentaufnahme als **ein** `INSERT … ON CONFLICT DO UPDATE`; PostgreSQL
bricht das ab (`CardinalityViolation: cannot affect row a second time`) und die
**ganze** Momentaufnahme war verloren. Die Dedupe-Menge im Code war toter Code.
Behoben (erster Treffer gewinnt, wie beim Merge) + Regressionstest
(`tests/test_cache.py`). Nicht exotisch: eine Antwort mit **mehreren
Scheduled Procedure Steps** erzeugt denselben Schlüssel ebenfalls.

### Fund 3 (unser Broker): eine zweite `handle_find` überschrieb die geteilte Aggregation

`dimse.py` hatte **zwei** Methoden `handle_find`; Python nimmt die letzte. Die
zweite implementierte den Fan-out **inline** statt über `aggregation.collect` —
und ihr fehlte die Absicherung um `cache.store_snapshot`. Damit wurde aus einem
**Cache-Schreibfehler ein Quellenfehler**: der Breaker öffnete, die gesunde
Quelle verschwand aus der Arbeitsliste (`status: partial`), und der
Operator-Vorschau-Trockenlauf log, weil er `collect()` benutzt. Das Duplikat ist
entfernt; ein Test (`test_c_find_runs_the_shared_aggregation`) erzwingt, dass der
Live-C-FIND die geteilte Aggregation nutzt.

## Was noch offen ist

**Nicht** geprüft ist DVTk gegen *unsere* Conformance-Erklärung: dafür bräuchte
es eine eigene Definition-Datei unseres Systems (die 2024a-Standard-Dateien sind
kommerziell). DVTk prüft gegen den **DICOM-Standard** — das ist der Nachweis, den
die Tabelle oben führt.

**Was einen Menschen braucht:** die Emulatoren mit Oberfläche müssen **gestartet**
werden (Klick am Gerät) — danach sind sie über den SSH-Tunnel erreichbar, der
RIS-Emulator lief genau so. Der **Storage-SCP braucht keine Oberfläche**:
`DVTCmd -estscp` fährt ihn aus der Konsole, `dvtk_emulator.py` hält dabei das
stdin offen (das war die eigentliche Hürde, nicht die fehlende
Kommandozeilensteuerung).

**Was auf dieser Maschine (noch) nicht liegt:** der *Modality Emulator* — seine
Rolle (fremde Modalität: MWL + MPPS + C-STORE) decken zwei Werkzeuge ab, die
schon laufen: DVTks Skriptmodus als SCU und DCMTK. Der *Query/Retrieve
SCP Emulator* ist vorhanden, aber für uns ohne Anwendung: der Broker ist kein
Q/R-SCU (das macht OE3/OHIF). Ungenutzt und jederzeit verfügbar sind außerdem
der **DICOM Network Analyzer** und **DICOM Compare**.
