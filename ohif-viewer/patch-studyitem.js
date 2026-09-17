// Patch script for StudyItem.tsx and StudyBrowser.tsx
// Adds patient data display (name, MRN, accession, birth date) and
// formats dates as DD.MM.YYYY in the native StudyBrowser left panel.
const fs = require('fs');

// === Patch 1: StudyItem.tsx ===
const itemPath = 'platform/ui-next/src/components/StudyItem/StudyItem.tsx';

if (!fs.existsSync(itemPath)) {
  console.error('FEHLER: Datei nicht gefunden:', itemPath);
  process.exit(1);
}

let item = fs.readFileSync(itemPath, 'utf8');

// Idempotenz-Pruefung
if (item.includes('patch-studyitem')) {
  console.log('StudyItem.tsx: Patch bereits angewendet, ueberspringe.');
} else {

  // Add helper functions after Tooltip import
  const before1 = item;
  item = item.replace(
    "import { Tooltip, TooltipContent, TooltipTrigger } from '../Tooltip';",
    "import { Tooltip, TooltipContent, TooltipTrigger } from '../Tooltip';\n\n" +
    "// patch-studyitem: Helper fuer Datums- und Patientenname-Formatierung\n" +
    "const _fmtDate = (d) => { if (!d || d.length !== 8 || !/^[0-9]+$/.test(d)) return d || ''; return d.substring(6,8) + '.' + d.substring(4,6) + '.' + d.substring(0,4); };\n" +
    "const _fmtPN = (pn) => { if (!pn) return ''; if (typeof pn === 'object' && pn.Alphabetic) pn = pn.Alphabetic; const p = String(pn).split('^'); return p[1] ? p[0] + ', ' + p[1] : p[0]; };"
  );
  if (item === before1) {
    console.error('FEHLER: Tooltip-Import-Marker in StudyItem.tsx nicht gefunden.');
    process.exit(1);
  }

  // Add new props to function signature
  item = item.replace(
    'StudyInstanceUID,',
    'StudyInstanceUID,\n  patientName,\n  mrn,\n  accession,\n  patientBirthDate,'
  );

  // Replace {date} with {_fmtDate(date)} - only in JSX context (not in comments/strings)
  item = item.replace(/{date}/g, '{_fmtDate(date)}');

  // Increase height from h-[40px] to min-h-[60px] for 3 lines
  item = item.replace('h-[40px]', 'min-h-[60px]');

  // Insert patient info div after the second Tooltip (description) closing tag
  // and before the closing </div> of the flex column
  item = item.replace(
    /(<\/Tooltip>\s*\n)(\s*<\/div>\s*\n\s*<div className="text-muted-foreground flex flex-col)/,
    '$1' +
    '                <div className="text-muted-foreground h-[16px] w-full overflow-hidden truncate whitespace-nowrap text-left text-[11px]">' +
    '{_fmtPN(patientName)}{mrn ? " | MRN: " + mrn : ""}{accession ? " | Acc: " + accession : ""}' +
    '{patientBirthDate ? " | Geb: " + _fmtDate(patientBirthDate) : ""}</div>\n' +
    '$2'
  );

  fs.writeFileSync(itemPath, item);
  console.log('StudyItem.tsx patched: patient data + date formatting');
}

// === Patch 2: StudyBrowser.tsx ===
const browserPath = 'platform/ui-next/src/components/StudyBrowser/StudyBrowser.tsx';

if (!fs.existsSync(browserPath)) {
  console.error('FEHLER: Datei nicht gefunden:', browserPath);
  process.exit(1);
}

let browser = fs.readFileSync(browserPath, 'utf8');

// Idempotenz-Pruefung
if (browser.includes('patientBirthDate={patientBirthDate}')) {
  console.log('StudyBrowser.tsx: Patch bereits angewendet, ueberspringe.');
} else {

  // Add patient fields to destructuring
  browser = browser.replace(
    '{ studyInstanceUid, date, description, numInstances, modalities, displaySets }',
    '{ studyInstanceUid, date, description, numInstances, modalities, displaySets, patientName, mrn, accession, patientBirthDate }'
  );

  // Add patient props to StudyItem element
  browser = browser.replace(
    'StudyInstanceUID={studyInstanceUid}',
    'StudyInstanceUID={studyInstanceUid}\n' +
    '              patientName={patientName}\n' +
    '              mrn={mrn}\n' +
    '              accession={accession}\n' +
    '              patientBirthDate={patientBirthDate}'
  );

  fs.writeFileSync(browserPath, browser);
  console.log('StudyBrowser.tsx patched: patient props passed to StudyItem');
}
