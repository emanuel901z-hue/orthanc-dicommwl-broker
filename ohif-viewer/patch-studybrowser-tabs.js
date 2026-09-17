/**
 * patch-studybrowser-tabs.js
 *
 * Patcht platform/core/src/utils/createStudyBrowserTabs.ts:
 * Studien, die ueber den PACS Browser geladen wurden, erscheinen
 * normalerweise nicht im StudyBrowser links, da dieser seine Liste
 * aus QIDO-Suchen nach Patienten-MRN aufbaut. Der Patch fuegt
 * DisplaySets, deren StudyInstanceUID nicht in studyDisplayList ist,
 * als zusaetzliche Studien hinzu, damit sie im StudyBrowser erscheinen.
 *
 * Patientendaten werden aus DicomMetadataStore geholt.
 *
 * Ausgelagert aus dem Dockerfile (war ein 1000+ Zeichen sed-Patch).
 * Diese Version ist robuster: prueft ob das Pattern existiert und
 * gibt einen Fehler zurueck wenn nicht.
 */
const fs = require('fs');
const path = require('path');

// Pfad relativ zum Arbeitsverzeichnis (WORKDIR /app im Docker-Build).
const filePath = path.join(process.cwd(), 'platform', 'core', 'src', 'utils', 'createStudyBrowserTabs.ts');

if (!fs.existsSync(filePath)) {
  console.error('FEHLER: Datei nicht gefunden:', filePath);
  process.exit(1);
}

let src = fs.readFileSync(filePath, 'utf8');

// Pruefen ob Patch bereits angewendet wurde.
if (src.includes('extension-radiology-advanced StudyBrowser Patch')) {
  console.log('createStudyBrowserTabs.ts: Patch bereits angewendet, ueberspringe.');
  process.exit(0);
}

// Pruefen ob das Ziel-Pattern existiert.
const marker = 'const primaryStudiesTimestamps';
if (!src.includes(marker)) {
  console.error('FEHLER: Marker "' + marker + '" nicht in createStudyBrowserTabs.ts gefunden.');
  console.error('OHIF-Version moeglicherweise inkompatibel. Abbruch.');
  process.exit(1);
}

// Der einzufuegende Code (als Block-Kommentar + Code).
const insertCode = `
  // extension-radiology-advanced StudyBrowser Patch: DisplaySets, deren
  // StudyInstanceUID nicht in studyDisplayList ist, als zusaetzliche Studien
  // hinzufuegen, damit sie im StudyBrowser erscheinen.
  const { DicomMetadataStore } = require('@ohif/core');
  displaySets.forEach(ds => {
    if (ds.StudyInstanceUID && !allStudies.find(s => s.studyInstanceUid === ds.StudyInstanceUID)) {
      const o = displaySetService.getDisplaySetByUID(ds.displaySetInstanceUID);
      if (o) {
        let _sd='',_dd='',_mm='',_pn='',_pid='',_acc='',_bd='';
        const _st = DicomMetadataStore && DicomMetadataStore.getStudy(ds.StudyInstanceUID);
        if (_st) {
          _sd = _st.StudyDate || '';
          _dd = _st.StudyDescription || '';
          _pn = _st.PatientName || '';
          _pid = _st.PatientID || '';
          _acc = _st.AccessionNumber || '';
          _mm = (_st.ModalitiesInStudy || []).join(', ');
          if (_st.series && _st.series[0] && _st.series[0].instances && _st.series[0].instances[0]) {
            _bd = _st.series[0].instances[0].PatientBirthDate || '';
            if (!_pn) _pn = _st.series[0].instances[0].PatientName || '';
            if (!_pid) _pid = _st.series[0].instances[0].PatientID || '';
            if (!_acc) _acc = _st.series[0].instances[0].AccessionNumber || '';
            if (!_sd) _sd = _st.series[0].instances[0].StudyDate || '';
            if (!_dd) _dd = _st.series[0].instances[0].StudyDescription || '';
          }
        }
        if (!_sd) _sd = o.StudyDate || '';
        if (!_dd) _dd = o.StudyDescription || '';
        if (!_mm) _mm = o.Modality || '';
        allStudies.push({
          studyInstanceUid: ds.StudyInstanceUID,
          date: _sd,
          description: _dd,
          modalities: _mm,
          patientName: _pn,
          mrn: _pid,
          accession: _acc,
          patientBirthDate: _bd,
          numInstances: displaySets.filter(d => d.StudyInstanceUID === ds.StudyInstanceUID).length,
          displaySets: displaySets.filter(d => d.StudyInstanceUID === ds.StudyInstanceUID),
        });
      }
    }
  });
`;

// Code vor dem Marker einfuegen.
const before = src;
src = src.replace(
  new RegExp('(.*?)' + marker),
  insertCode + '\n' + marker
);
if (src === before) {
  console.error('FEHLER: Replace hatte keine Wirkung. Marker "' + marker + '" nicht gefunden.');
  process.exit(1);
}

fs.writeFileSync(filePath, src);
console.log('createStudyBrowserTabs.ts gepatcht: DisplaySet-Studien im StudyBrowser sichtbar.');
