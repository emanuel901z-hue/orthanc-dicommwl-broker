// Patch script for formatContentItem.ts in cornerstone-dicom-sr extension.
// Problem: Der Carestream PACS liefert einige SR-Werte als Bulk-Data-Referenz
// ({BulkDataURI, retrieveBulkData}) statt als inline String. Die Formatter
// geben dieses Objekt zurueck, und React stuerzt mit Error #31 ab, wenn
// versucht wird, ein Objekt als Child zu rendern.
// Loesung: Wrapper um jeden Formatter, der Objekte in Platzhalter-Strings
// umwandelt. Zusaetzlich wird versucht, den BulkDataURI-Inhalt asynchron
// nachzuladen.
const fs = require('fs');

const p = 'extensions/cornerstone-dicom-sr/src/utils/formatContentItem.ts';

// Datei-Existenz-Pruefung
if (!fs.existsSync(p)) {
  console.error('FEHLER: Datei nicht gefunden:', p);
  process.exit(1);
}

let s = fs.readFileSync(p, 'utf8');

// Idempotenz-Pruefung
if (s.includes('patch-sr-bulkdata')) {
  console.log('formatContentItem.ts: Patch bereits angewendet, ueberspringe.');
  process.exit(0);
}

// Add a helper function that safely resolves bulk data values
const helperCode = `
// patch-sr-bulkdata: Bulk-Data-Objekt erkennen: {BulkDataURI, retrieveBulkData} oder {InlineBinary}
function _safeValue(v) {
  if (v === null || v === undefined) return undefined;
  if (typeof v === 'string') return v;
  if (typeof v === 'number') return String(v);
  if (typeof v === 'object') {
    // Bulk-Data-Referenz: versuche asynchrones Nachladen
    if (v.retrieveBulkData && typeof v.retrieveBulkData === 'function') {
      // Asynchrones Nachladen anstossen, aber synchron Platzhalter zurueckgeben
      v.retrieveBulkData().then(data => {
        // Wert kann nicht synchron in React eingefuegt werden,
        // daher nur Logging. Eine vollstaendige Loesung erfordert
        // eine State-Aktualisierung in der SR-Komponente.
        console.debug('[SR] Bulk Data nachgeladen:', data);
      }).catch(err => {
        console.warn('[SR] Bulk data Nachladen fehlgeschlagen:', err);
      });
      return '[Bulk data - wird nachgeladen]';
    }
    if (v.BulkDataURI) return '[Bulk data: ' + v.BulkDataURI.substring(0, 50) + ']';
    if (v.InlineBinary) return '[Inline binary data]';
    // Anderes Objekt: JSON-Repraesentation als Fallback
    try { return JSON.stringify(v); } catch { return '[Objekt]'; }
  }
  return String(v);
}
`;

// Insert helper function before contentItemFormatters
const before = s;
s = s.replace(
  'const contentItemFormatters = {',
  helperCode + '\nconst contentItemFormatters = {'
);
if (s === before) {
  console.error('FEHLER: Marker "const contentItemFormatters = {" nicht gefunden.');
  process.exit(1);
}

// Wrap each formatter to use _safeValue - track replacements
let replaceCount = 0;
function safeReplace(src, oldStr, newStr) {
  if (src.includes(oldStr)) {
    replaceCount++;
    return src.replace(oldStr, newStr);
  }
  console.warn('WARN: Marker nicht gefunden: ' + oldStr.substring(0, 60));
  return src;
}

s = safeReplace(s, 'TEXT: contentItem => contentItem.TextValue,', 'TEXT: contentItem => _safeValue(contentItem.TextValue),');
s = safeReplace(s, 'CODE: contentItem => contentItem.ConceptCodeSequence?.[0]?.CodeMeaning,', 'CODE: contentItem => _safeValue(contentItem.ConceptCodeSequence?.[0]?.CodeMeaning),');
s = safeReplace(s, 'UIDREF: contentItem => contentItem.UID,', 'UIDREF: contentItem => _safeValue(contentItem.UID),');
s = safeReplace(s, 'return `${NumericValue} ${CodeValue}`;', 'return _safeValue(`${NumericValue} ${CodeValue}`);');
s = safeReplace(s, 'return personName ? utils.formatPN(personName) : undefined;', 'return personName ? _safeValue(utils.formatPN(personName)) : undefined;');
s = safeReplace(s, 'return Date ? utils.formatDate(Date) : undefined;', 'return Date ? _safeValue(utils.formatDate(Date)) : undefined;');
s = safeReplace(s, 'return Time ? utils.formatTime(Time) : undefined;', 'return Time ? _safeValue(utils.formatTime(Time)) : undefined;');
s = safeReplace(s, 'return `${formattedDate} ${formattedTime}`;', 'return _safeValue(`${formattedDate} ${formattedTime}`);');

if (replaceCount === 0) {
  console.error('FEHLER: Keine der Formatter-Marker wurde gefunden. OHIF-Version inkompatibel?');
  process.exit(1);
}

fs.writeFileSync(p, s);
console.log(`formatContentItem.ts gepatcht: ${replaceCount} Formatter gewrapped, Bulk-Data-Objekte werden sicher behandelt.`);
