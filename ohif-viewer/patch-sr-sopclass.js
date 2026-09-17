/**
 * patch-sr-sopclass.js
 *
 * Patcht extensions/cornerstone-dicom-sr/src/getSopClassHandlerModule.ts:
 *
 * Problem: Der dicom-sr Handler unterstuetzt nur 4 SOP Classes:
 *   - BasicTextSR (88.11)
 *   - EnhancedSR (88.22)
 *   - ComprehensiveSR (88.33)
 *   - Comprehensive3DSR (88.34)
 *
 * Weitere SR-Typen wie XRayRadiationDoseSR (88.67, Dosisbericht),
 * MammographyCADSR (88.50), ChestCADSR (88.65), etc. werden nicht
 * erkannt und als "unsupported" markiert.
 *
 * Fix: Erweitere die sopClassUids-Array um alle verfuegbaren SR-Typen
 * aus dem sopClassDictionary.
 */
const fs = require('fs');
const path = require('path');

const targetPath = path.join(
  process.cwd(),
  'extensions/cornerstone-dicom-sr/src/getSopClassHandlerModule.ts'
);

if (!fs.existsSync(targetPath)) {
  console.error('FEHLER: Datei nicht gefunden:', targetPath);
  process.exit(1);
}

let src = fs.readFileSync(targetPath, 'utf8');

if (src.includes('patch-sr-sopclass')) {
  console.log('getSopClassHandlerModule.ts: Patch bereits angewendet.');
} else {
  const oldCode = `const sopClassUids = [
  sopClassDictionary.BasicTextSR,
  sopClassDictionary.EnhancedSR,
  sopClassDictionary.ComprehensiveSR,
  sopClassDictionary.Comprehensive3DSR,
];`;

  const newCode = `const sopClassUids = [
  sopClassDictionary.BasicTextSR,
  sopClassDictionary.EnhancedSR,
  sopClassDictionary.ComprehensiveSR,
  sopClassDictionary.Comprehensive3DSR,
  // patch-sr-sopclass: Zusaetzliche SR-Typen fuer klinische PACS
  sopClassDictionary.XRayRadiationDoseSR,
  sopClassDictionary.RadiopharmaceuticalRadiationDoseSR,
  sopClassDictionary.MammographyCADSR,
  sopClassDictionary.ChestCADSR,
  sopClassDictionary.ColonCADSR,
].filter(uid => {
  if (!uid) {
    console.warn('patch-sr-sopclass: SOP Class Dictionary Eintrag fehlt, wird uebersprungen');
    return false;
  }
  return true;
});`;

  if (src.includes(oldCode)) {
    src = src.replace(oldCode, newCode);
    fs.writeFileSync(targetPath, src);
    console.log('getSopClassHandlerModule.ts gepatcht: 5 zusaetzliche SR-Typen hinzugefuegt.');
  } else {
    console.error('FEHLER: Marker fuer sopClassUids nicht gefunden.');
    process.exit(1);
  }
}

console.log('Patch abgeschlossen: SR-SOP-Class-Handler erweitert.');
