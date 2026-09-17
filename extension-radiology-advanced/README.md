# extension-radiology-advanced

OHIF v3 Extension fuer erweiterte radiologische Funktionen, die in
OHIF v3.12.5 nicht out-of-the-box verfuegbar sind.

## Funktionen

### 1. sameAs Custom Attribute (Hanging Protocol)

Registriert das Custom Attribute `sameAs` beim HangingProtocolService.
Ermöglicht das Matching von DisplaySets ueber gemeinsame Attribute,
z.B. `FrameOfReferenceUID` fuer PET/CT-Fusion.

Verwendung in Hanging Protocols:

```javascript
displaySetSelectors: {
  ptDisplaySet: {
    seriesMatchingRules: [
      {
        attribute: 'sameAs',
        sameAttribute: 'FrameOfReferenceUID',
        sameDisplaySetId: 'ctDisplaySet',
        constraint: { equals: { value: true } },
      },
    ],
  },
},
```

### 2. TIC Panel (Time-Intensity Curve)

Panel in der Seitenleiste fuer ROI-basierte Zeit-Intensitaets-Kurven
in 4D/dynamischen Volumina (Perfusion, dynamisches CT/MR).

- Erkennt automatisch 4D-DisplaySets
- Sammelt ROI-Statistiken (Mean) ueber Zeitpunkte aus
  `measurement.data` (cachedStats, keyed by imageId)
- Zeichnet SVG-Linien-Kurve
- Voraussetzung: ROI-Annotation (Rectangle/Elliptical) im Bild

### 3. Mismatch Panel (Mismatch Analysis)

Panel fuer Volumen-Vergleich durch Subtraktion zweier Bildserien.

- Auswahl von Basis- und Vergleichs-DisplaySet
- Overlay des Vergleichs-Volumens mit Hot-Colormap
- Anwendungen: Perfusions-Mismatch, Pre/Post-Kontrast

### 4. Vessel Tracking Panel

Info-Panel fuer gefaessspezifische Bildanalyse.

- Wechsel zu MIP/MPR+MIP Hanging Protocols
- Anleitung zur manuellen Gefaessvermessung
- Liste verfuegbarer Mess-Tools (Length, Angle, ROI, etc.)
- Hinweis: Automatisiertes Gefaesstracking erfordert Custom-Tool-Entwicklung

### 5. PACS Browser Panel

QIDO-RS-Studiensuche direkt im Viewer.

- Standardfelder: Patientenname, MRN, Accession, Datum, Modality,
  Beschreibung
- Erweiterte clientseitige Filter ueber private Carestream/Elscint-Tags
  (Site ID 07A31015, Origin AE 07A51069, Region 07A11040,
  Station 00081010)
- Favoriten und Suchverlauf in localStorage
- Gefundene Studien per Klick in den Viewer ladbar (loadStudy-Command)
- Drag&Drop in Viewports

Vier Tabs:

- **Suche**: QIDO-Suche mit Standard- und erweiterten Filtern
- **Geladen**: Alle im Viewer aktiven Studien mit Patientendaten
  (Name, MRN, Geburtsdatum, Untersuchungsdatum, Beschreibung,
  Modality, Accession, Serien-/Bildanzahl). Aktualisiert sich
  automatisch ueber displaySetService-Events.
- **Favoriten**: Gespeicherte Studien (localStorage)
- **Verlauf**: Letzte Suchanfragen (localStorage)

StudyBrowser-Integration: Im Dockerfile wird `createStudyBrowserTabs.ts`
gepatcht, damit Studien aus dem PACS Browser (auch andere Patienten)
im nativen StudyBrowser links im "Alle"-Tab erscheinen. Patientendaten
(Name, MRN, Accession, Geburtsdatum) werden aus `DicomMetadataStore`
geholt, da DisplaySets diese nicht direkt enthalten.

Der native StudyBrowser wird via `patch-studyitem.js` gepatcht
(`StudyBrowser.tsx` + `StudyItem.tsx`), um pro Studie drei Zeilen
anzuzeigen: Datum (DD.MM.YYYY) + Beschreibung, Patientendaten
(Name, MRN, Accession, Geburtsdatum), Modality + Bildanzahl.

QIDO-Suchergebnisse werden clientseitig nach Relevanz sortiert:
Exakter Treffer (Score 100) > beginnt-mit (80) > enthaelt (60) >
Fuzzy (40/20). Bei gleichem Score nach Datum absteigend.

### 6. Fensterungs-Presets Panel

Modalitaetsspezifische W/L-Presets.

- CT: Hirn, Knochen, Lunge, Abdomen, Mediastinum, CTA
- MR: T1, T2, FLAIR, DWI, SWI
- DX: Thorax, Knochen, Mamma
- PT: PET-SUV
- XA: DSA
- Modality wird automatisch aus dem aktiven Viewport erkannt

### 7. ROI-Statistik Panel

Live-HU/Signal-Auslesung und ROI-Statistiken.

- Cursor-Position mit HU-Wert in Echtzeit
- Statistiken (Mean/Min/Max/StdDev/Area) fuer alle aktiven ROI-
  Annotationen (RectangleROI, EllipticalROI, CircleROI)
- Werte werden aus `measurement.data` (cachedStats) gelesen,
  NICHT aus `measurement.stats` (immer leer in OHIF v3)
- NaN-Check fuer alle Werte, displayText-Fallback (parse Mean/Max
  aus `displayText.primary` wenn cachedStats noch nicht berechnet)
- Klick auf eine ROI-Zeile springt zur entsprechenden Instanz
  (`jumpToMeasurementViewport` Command)
- Refresh-Button fuer manuelle Aktualisierung der Statistiken
- Hover-Effekt und Tooltip fuer ROI-Zeilen
- Automatische Aktualisierung bei Messungs-Aenderungen
- Schritt-fuer-Schritt-Anleitung im Panel

### 8. DICOM-Tag-Browser Panel

Vollstaendige Tag-Anzeige einer Serie.

- Alle DICOM-Tags inkl. privater Carestream/Elscint-Tags
- Suche nach Tag-Name oder Tag-Nummer
- Filter nach Tag-Gruppen (Patient/Studie/Serie/Bild/Akquisition/Private)
- Klick-zum-Kopieren
- Datumsformatierung (YYYYMMDD -> DD.MM.YYYY)

### 9. Studien-Vergleich/Sync Panel

Synchronisierte Darstellung mehrerer Viewports.

- Sync-Optionen: Scrollen, Zoom, Pan, Window/Level
- Side-by-Side-Layout fuer Prior-Vergleich
- Nutzt `toggleSynchronizer` Command (OHIF v3 API)
- Schritt-fuer-Schritt-Anleitung fuer Studien-Vergleich im Panel

### 10. Cine/4D-Navigation Panel

Steuerung fuer Cine-Wiedergabe und 4D-Navigation.

- Play/Pause
- Frame-Slider
- Geschwindigkeitsregler (1-30 fps)
- Loop-Modi (Endlos/Einmal/Ping-Pong)
- Ergaenzt TIC-Panel fuer dynamische Serien

### 11. Messungs-Export Panel

Export aller Messungen.

- CSV-Export mit Header, Werten und Escaping
- JSON-Export
- DICOM SR (Structured Report) Export (erfordert dcmjs)
- Werte aus `measurement.data` (cachedStats) fuer Mean/StdDev/
  Area/Length/Angle
- Download oder Zwischenablage-Kopie

### 12. MPR/Slab Controls Panel

Inline-Steuerung fuer MPR und Slab-Rendering.

- Orientierung (Axial/Sagittal/Koronar)
- Blend-Mode (MIP/minIP/Avg/Off) ueber `setBlendMode(enumValue)`
  (nicht `setProperties` - Cornerstone3D API)
- Slab-Dicke (0-100mm mit Quick-Presets)
- Viewport-Type-Umschaltung (Stack/Volume/3D)
- VolumeViewport-Check: MIP/Slab nur in Volume-Viewports
- Schritt-fuer-Schritt-Anleitung fuer MPR/MIP im Panel

### 13. Hotkey-Hilfe Panel

Uebersicht aller Tastenkuerzel.

- Suchfunktion nach Tastenkuerzel oder Befehlsname
- Kategorisierung (Viewport/Navigation/Messung/Fensterung/Cine/
  Scroll/Layout/Werkzeug)
- Anzeige der aktiven Tastenkuerzel aus window.config.hotkeys

## Build-Integration

Die Extension wird beim Docker-Build in den OHIF-Quelltext kopiert
und ueber `pluginConfig.json` registriert. Zusaetzlich muessen die
OHIF-Mode-Dateien (modes/basic/src/index.tsx, modes/longitudinal/
src/index.ts) gepatcht werden, um die Extension in
`extensionDependencies` aufzunehmen und die Panel-Module in
`rightPanels` einzutragen. Siehe `ohif-viewer/Dockerfile`.

Die Patch-Scripts (`patch-studybrowser-tabs.js`, `patch-studyitem.js`,
`patch-sr-bulkdata.js`, `patch-unsupported-displayset.js`,
`patch-dynamic-volume.js`, `patch-sr-sopclass.js`) pruefen, ob die
Ziel-Marker existieren, und schlagen mit Exit-Code 1 fehl, wenn die
OHIF-Version inkompatibel ist. `check-patches.js` verifiziert nach dem
Patchen, dass alle kritischen Patches angewendet wurden.

Zusaetzlich werden in der `pluginConfig.json` 7 OHIF-Extensions
(SR, PDF, SEG, RT, PMAP, Video, dynamic-volume) auf `default: true`
gesetzt, damit deren `sopClassHandler` immer geladen werden. Ohne
diesen Patch werden SR/PDF/SEG-DisplaySets als "unsupported" markiert.

## Error Boundaries

Alle 12 Panels sind in eine `PanelErrorBoundary`-Komponente gewrappt
(`getPanelModule.js`). Ein Runtime-Fehler in einem Panel fuehrt zu
einer Fehleranzeige im Panel selbst (Panel-Name + Fehlermeldung +
"Erneut versuchen"-Button), nicht zum Absturz der gesamten OHIF-App.
Dies ist besonders wichtig, da die Panels auf verschiedene OHIF-Services
zugreifen (cineService, displaySetService, measurementService etc.),
die je nach geladenem Modus unterschiedlich verfuegbar sein koennen.

## Dateistruktur

```text
extension-radiology-advanced/
  package.json               Extension-Metadaten
  README.md                  Dieses Dokument
  src/
    index.js                 Haupt-Einstiegspunkt
    id.js                    Eindeutige Extension-ID
    sameAs.js                Custom Attribute fuer HP-Matching
    getPanelModule.js        Panel-Registrierung (12 Panels mit Error Boundary)
    getHangingProtocolModule.js Registriert 80 Hanging Protocols
    getCommandsModule.js     Command-Registrierung (loadStudyFromPacs,
                             Mismatch, Protocol-Switch)
    panels/
      TICPanel.jsx           Time-Intensity Curve Panel
      MismatchPanel.jsx      Mismatch Analysis Panel
      VesselTrackingPanel.jsx Vessel Tracking Info Panel
      PacsBrowserPanel.jsx   QIDO-RS-Studiensuche
      WindowLevelPresetsPanel.jsx W/L-Presets
      ROIStatsPanel.jsx      ROI-Statistiken
      DicomTagBrowserPanel.jsx DICOM-Tag-Browser
      StudyComparePanel.jsx  Studien-Vergleich/Sync
      CineNavigationPanel.jsx Cine/4D-Navigation
      MeasurementExportPanel.jsx Messungs-Export
      MPRSlabControlsPanel.jsx MPR/Slab Controls
      HotkeyHelpPanel.jsx    Hotkey-Hilfe
```

## Runtime-Regeln

- `viewportGridService.getState().viewports` ist ein Object (Record),
  kein Array. `Object.values()` verwenden fuer Array-Operationen.
- `viewportGridService.EVENTS` kann undefined Events enthalten.
  Vor `subscribe()` pruefen: `if (evt && service.subscribe)`.
- `extensionMgr.getActiveDataSource()` kann undefined oder ein leeres
  Array zurueckgeben. Optional Chaining verwenden:
  `extensionMgr?.getActiveDataSource?.()` und auf Laenge > 0 pruefen.
- Cine-State nicht aus React-Closure lesen (stale closure), sondern
  aus `cineService.getCine(viewportId)` (aktueller Service-State).
- Panel-Buttons haben `data-cy="[panelName]-btn"`, Panel-Inhalte
  `data-cy="[panelName]"` (mit Bindestrichen).
- ROI-Statistiken liegen in `measurement.data` (cachedStats, keyed
  by imageId), NICHT in `measurement.stats` (immer leer in OHIF v3).
- `setBlendMode(enumValue)` verwenden, nicht `setProperties({blendMode})`.
  BlendMode-Enums: 0=COMPOSITE, 1=MAX, 2=MIN, 3=AVG.
- `toggleSynchronizer({type, viewports, syncId})` verwenden, nicht
  `setSynchronizerGroup` (existiert nicht in OHIF v3.12.5).
- `toggleCine()` verwenden, nicht `playCine`/`pauseCine` (existieren
  nicht in OHIF v3.12.5).
- `setViewportGridLayout({numRows, numCols})` verwenden, nicht
  `setViewportLayout` (existiert nicht).
- Toolbar: ROI-Tools (EllipticalROI, RectangleROI, CircleROI) sind
  im Dropdown `MeasurementTools-split-button-secondary` (Pfeil neben
  Length-Button). Weitere Tools im Dropdown `MoreTools-split-button-
  secondary`.
- `window.config` kann undefined sein (z.B. in Test-Umgebungen).
  Zugriff mit `typeof window !== 'undefined' && window && window.config`
  absichern.
- React-Keys: Keine Array-Indizes (`key: i`) als React-Key verwenden,
  sondern eindeutige IDs (uid, tag, name, timestamp) mit Index als
  Fallback. Aenderungen in Sortierung/Filterung fuehren sonst zu
  falschem DOM-Diffing.
- `setTimeout` in `useCallback` muss in einem `useRef` gespeichert
  und bei Unmount in `useEffect`-Cleanup abgebrochen werden.

## Bug-Fixes (Audit)

Folgende Bugs wurden in einem umfassenden Audit identifiziert und
behoben:

| Panel / Datei | Bug | Fix |
|---------------|-----|-----|
| `ROIStatsPanel.jsx` | `updateMeasurements()` ReferenceError beim Refresh-Klick (Funktion nur in `useEffect` definiert) | `useCallback` im Component-Scope, `activeModalityRef` fuer aktuellen State |
| `PacsBrowserPanel.jsx` | `getActiveDataSource()[0]` ohne Null-Check -> TypeError bei fehlender DataSource | Optional Chaining `extensionMgr?.getActiveDataSource?.()` + Leer-Check |
| `CineNavigationPanel.jsx` | Stale Closure: `isPlaying` aus React-State in `useCallback` -> falscher Toggle-State | State aus `cineService.getCine(viewportId)` lesen (Service-Source of truth) |
| `PacsBrowserPanel.jsx` | `setTimeout` in `repeatSearch` ohne Cleanup bei Unmount -> State-Update auf ungemountete Komponente | `repeatSearchTimeoutRef` + `useEffect`-Cleanup mit `clearTimeout` |
| `MeasurementExportPanel.jsx` | UID-Generierung mit `Math.random()` allein -> Kollisionen bei gleichzeitiger Generierung | Timestamp + monotoner Counter (`generateUID._counter`) + Random |
| `HotkeyHelpPanel.jsx` | `window.config?.hotkeys` ohne `typeof window`-Check -> ReferenceError in SSR/Test | Sichere Zugriff mit `typeof window !== 'undefined'` |
| `ROIStatsPanel.jsx` | Unvollstaendige Event-Listener (leere try/catch-Bloecke fuer Cornerstone3D Probe-Tool) | Unvollstaendigen Code entfernt, TODO-Kommentar fuer zukuenftige Implementierung |
| `TICPanel.jsx` | Platzhalter-Logik nicht als TODO markiert | TODO-Kommentar hinzugefuegt |
| `getPanelModule.js` | Keine Error Boundaries -> Panel-Fehler bringt gesamte OHIF-App zum Absturz | `PanelErrorBoundary`-Wrapper fuer alle 12 Panels |
| `MeasurementExportPanel.jsx` | `key: i` (Array-Index) als React-Key | `key: m.uid \|\| m.index \|\| i` |
| `PacsBrowserPanel.jsx` | `key: i` im Verlauf-Tab | `key: entry.timestamp \|\| i` |
| `WindowLevelPresetsPanel.jsx` | `key: i` in Preset-Liste | `key: preset.name \|\| i` |
| `HotkeyHelpPanel.jsx` | `key: i` in Hotkey-Liste | `key: h.command \|\| h.label \|\| i` |
| `DicomTagBrowserPanel.jsx` | `key: i` in Tag-Liste | `key: t.tag \|\| i` |
| OHIF Core (`commandsModule.ts`) | `addDisplaySetAsLayer` wirft "Unsupported displaySet" bei Klick auf unsupported Thumbnails (SR, PDF, SC) -> App-Absturz | `patch-unsupported-displayset.js`: Guard in `canAddDisplaySetToViewport` + `addDisplaySetAsLayer` |
| OHIF Core (`pluginConfig.json`) | SR/PDF/SEG/RT/PMAP/Video Extensions mit `default: false` -> sopClassHandler nicht geladen -> DisplaySets "unsupported" | 7 Extensions auf `default: true` setzen im Dockerfile |
| OHIF Core (`getSopClassHandlerModule.js`) | `getDynamicVolumeInfo`, `isDisplaySetReconstructable` und `getDisplaySetMessages` stuerzen ab bei unvollstaendigen Metadaten (fehlende `PixelSpacing`/`ImageOrientationPatient`/`ImagePositionPatient` bei SC-Bildern) -> `TypeError: Cannot read properties of undefined (reading '0')` | `patch-dynamic-volume.js`: 3 try-catch-Blöcke um alle Funktionen, Fallback auf nicht-reconstructable |
| OHIF Core (`cornerstone-dicom-sr`) | dicom-sr Handler unterstuetzt nur 4 SR-SOP-Classes (88.11/22/33/34); Dosisbericht (88.67) und CAD-SRs fallen durch -> "SOP Class UID is not supported" | `patch-sr-sopclass.js`: 5 zusaetzliche SR-Typen zur `sopClassUids`-Array hinzufuegen |

## Einschraenkungen

- Die TIC-Implementierung ist eine Basis-Version (als TODO markiert).
  Fuer eine exakte pixelweise TIC muss pro Zeitpunkt die ROI-Statistik
  neu berechnet werden (Cornerstone3D volumeLoader-API). Aktuell wird
  der Mean-Wert der ersten ROI fuer alle Zeitpunkte verwendet.
- Die Mismatch-Implementierung legt das Vergleichs-Volume als Overlay
  ab. Fuer eine pixelweise Subtraktion mit Differenz-Volume ist eine
  erweiterte Implementierung erforderlich.
- Vessel Tracking ist als Info-Panel realisiert. Automatisierte
  Centerline-Extraktion erfordert eine eigene Cornerstone3D-Tool-
  Entwicklung (Vesselness-Filter, Marching Cubes).
- PACS Browser: Die erweiterten Filter (Site ID, Origin AE, Region,
  Station) erfordern einen WADO-RS-Metadata-Abruf pro Studie und
  sind daher nur nach asynchronem Metadata-Laden verfuegbar. Private
  Tags sind Carestream/Elscint-spezifisch und bei anderen PACS
  u.U. nicht vorhanden.
- PACS Browser: Der "Geladen"-Tab zeigt Studien aus dem
  displaySetService. Patientendaten werden aus `DicomMetadataStore`
  geholt (Study-Level + Instance-Level Fallback). Bei unvollstaendigen
  Metadaten koennen einzelne Felder als '(unbekannt)' erscheinen.
- StudyBrowser-Integration: Der Patch von `createStudyBrowserTabs.ts`
  fuegt DisplaySets ohne Matching-Study in `studyDisplayList` als
  zusaetzliche Studien hinzu. Diese erscheinen im "Alle"-Tab, aber
  nicht im "Primary"-Tab (da sie nicht aus der URL-Route stammen).
  Patientendaten werden aus `DicomMetadataStore` extrahiert.
- StudyItem-Patch: `StudyItem.tsx` und `StudyBrowser.tsx` werden via
  `patch-studyitem.js` gepatcht, um Patientendaten (Name, MRN,
  Accession, Geburtsdatum) und formatierte Daten (DD.MM.YYYY) im
  nativen StudyBrowser links anzuzeigen. Die Hoehe wird von `h-[40px]`
  auf `min-h-[60px]` erweitert (3 Zeilen statt 2).
- SidePanel-Patch: `h-[40px]` -> `min-h-[40px]` im Tab-Grid-Header,
  damit Tabs bei Platzmangel in mehrere Reihen umbrechen statt
  abgeschnitten zu werden.
- Relevanz-Sortierung: QIDO-Suchergebnisse werden clientseitig nach
  Match-Genauigkeit sortiert (exakt > beginnt-mit > enthaelt > Fuzzy),
  bei gleichem Score nach Datum absteigend.
