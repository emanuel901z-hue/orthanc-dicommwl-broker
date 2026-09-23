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

## Was das nicht ist

DVTk prüft gegen den **DICOM-Standard**, nicht gegen *unsere*
Conformance-Erklärung: dafür bräuchte es eine eigene Definition-Datei unseres
Systems (die 2024a-Standard-Dateien sind kommerziell). Die GUI-Emulatoren
(RIS/Modality/Storage-SCP) sind über SSH nicht fahrbar — sie haben keine
Kommandozeilensteuerung, und `DVTCmd -estscp` verlangt ein dauerhaft offenes
stdin.
