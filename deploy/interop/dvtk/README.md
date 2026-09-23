# DVTk-Skripte für die externe Validierung (E1, Teil 3)

Diese beiden Skripte werden mit **DVTk** (`DVTCmd.exe`, DICOM Validation Toolkit,
Philips/ICT Group — das Werkzeug, auf dem auch die IHE-RO-Validierung aufsetzt)
gegen den laufenden Broker gefahren. DVTk validiert jede empfangene Nachricht
gegen die **DICOM-Definition-Dateien** — eine Prüfung, die unsere eigenen Tests
nicht leisten können.

| Datei | Was sie tut | Ergebnis (Referenzlauf) |
|---|---|---|
| `mpps_interop.ds` | MPPS: `N-CREATE` (IN PROGRESS) + `N-SET` (COMPLETED) mit gültiger UID | **PASSED** — 0 Validierungsfehler |
| `mwl_interop.ds` | Modality Worklist `C-FIND` (Return-Keys deklariert) | Antwort kommt (3 Einträge, aus zwei Quellen aggregiert); DVTks *Testskript* meldet Wertabweichungen, weil es exakte Referenzwerte erwartet — strukturell keine VR-/Typfehler |

Zusätzlich gefahren (unveränderte DVTk-Beispiele): **C-ECHO** und **C-STORE**
(ein im Skript erzeugtes Secondary-Capture-Bild) — beide **PASSED**, der Store
landete nachweislich im Broker (`/logs/stores`: `DVTK_SCU … success`).

## Wie man sie fährt

Auf der Windows-Maschine (Beispielpfade):

```powershell
# 1. Beispiel-Sessions kopieren und auf den Broker zeigen lassen
#    (SUT-AE-TITLE/SUT-HOSTNAME/SUT-PORT in der .ses patchen)
# 2. Skript fahren
cd D:\Projekte\orthanc-dicommwl-broker\DVTkdvt\Bin
.\DVTCmd.exe "D:\...\Mpps_Scu\MPPS_SCU.ses" "D:\...\Mpps_Scu\mpps_interop.ds"
.\DVTCmd.exe "D:\...\Query_Scu\Query_SCU.ses" "D:\...\Query_Scu\mwl_interop.ds"
```

Die Session-Dateien der Beispiele liegen im DVTk-Quellbaum
(`DVT/Resources/Example/Scripts/...`); die Felder `SUT-AE-TITLE`,
`SUT-HOSTNAME` und `SUT-PORT` müssen auf den Broker zeigen.

## Zwei Befunde aus diesem Lauf

1. **DVTks eigenes MPPS-Beispiel ist fehlerhaft:** es sendet und erwartet die
   SOP-Instanz-UID `"MppsUID"` — keine gültige DICOM-UID. DVTks *eigener*
   Validator beanstandet das (`value should start with digit(s)`). Mit einer
   echten UID läuft dasselbe Szenario fehlerfrei durch (`mpps_interop.ds`).
2. **Unser MPPS-SCP ist bewusst nachsichtig:** ein `N-SET` ohne vorheriges
   `N-CREATE` wird angenommen und der Schritt gespeichert (Kommentar in
   `mpps.record_update`), statt mit `0x0112` (No Such SOP Instance) zu
   antworten. DICOM erlaubt die Ablehnung; DVTks Beispiel macht genau diesen
   Fall — die Nachsicht rettet die Information für das RIS.
