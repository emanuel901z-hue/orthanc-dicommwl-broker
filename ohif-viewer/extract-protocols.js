/**
 * Extrahiert Hanging Protocols aus default.js und schreibt sie
 * in modulare Dateien unter ohif-viewer/protocols/.
 *
 * Usage: node ohif-viewer/extract-protocols.js
 */
const fs = require('fs');
const path = require('path');

// default.js einlesen und sicher evaluieren (ohne eval).
// default.js weist window.config = {...} zu. Wir nutzen das Module-System
// statt eval(), indem wir den Code in eine temporäre CommonJS-Datei
// umschreiben und require() verwenden.
const code = fs.readFileSync(
  path.join(__dirname, 'default.js'), 'utf8'
);
const modifiedCode = code.replace('window.config =', 'module.exports =');
const tmpFile = path.join(__dirname, '.default-eval-tmp.js');
fs.writeFileSync(tmpFile, modifiedCode);
let config;
try {
  config = require(tmpFile);
} finally {
  fs.unlinkSync(tmpFile);
}

// Modul-Zuordnung: Dateiname -> Liste von Protokoll-IDs
const MODULE_MAP = {
  'generic.js': [
    'ct-default', 'ct-mpr', 'ct-mip', 'ct-mpr-mip',
    'mr-default', 'mr-mpr', 'dx-default', 'ptct-fusion',
  ],
  'ct-cranial.js': [
    'ct-cct', 'ct-cct-prior',
    'ct-cta', 'ct-cta-prior',
    'ct-cta-head', 'ct-cta-head-prior',
    'ct-perfusion',
    'ct-cta-perfusion', 'ct-cta-perfusion-prior',
    'ct-hwt',
  ],
  'ct-angio.js': [
    'ct-bba', 'ct-bba-prior',
    'ct-cta-aorta', 'ct-cta-aorta-prior',
    'ct-cta-peripheral',
  ],
  'ct-body-trauma.js': [
    'ct-hws', 'ct-hws-prior',
    'ct-thorax-abdomen', 'ct-thorax-abdomen-prior',
    'ct-ctab-spine', 'ct-ctab-spine-prior',
    'ct-mittelgesicht', 'ct-mittelgesicht-prior',
    'ct-abdomen', 'ct-abdomen-prior',
    'ct-osteo', 'ct-osteo-prior',
    'ct-polytrauma', 'ct-polytrauma-prior',
  ],
  'dx-skeleton.js': [
    'dx-thorax', 'dx-thorax-prior',
    'dx-spine', 'dx-spine-prior',
    'dx-extremity',
    'dx-hand', 'dx-hand-prior',
    'dx-pelvis', 'dx-pelvis-prior',
  ],
  'dx-extremity.js': [
    'dx-elbow', 'dx-elbow-prior',
    'dx-wrist', 'dx-wrist-prior',
    'dx-knee', 'dx-knee-prior',
    'dx-ankle', 'dx-ankle-prior',
    'dx-foot', 'dx-foot-prior',
    'dx-lower-leg', 'dx-lower-leg-prior',
    'dx-sacrum', 'dx-sacrum-prior',
    'dx-abdomen', 'dx-abdomen-prior',
  ],
  'mr.js': [
    'mr-spine', 'mr-spine-prior',
    'mr-angio-head', 'mr-angio-head-prior',
    'mr-angio-aorta', 'mr-angio-peripheral',
  ],
  'xa-dsa.js': [
    'xa-default',
    'xa-dsa-head', 'xa-dsa-head-prior',
    'xa-dsa-carotid',
    'xa-dsa-aorta',
    'xa-dsa-peripheral',
    'xa-dsa-coronary',
  ],
};

// Protokolle nach ID indizieren
const byId = {};
config.hangingProtocols.forEach(hp => { byId[hp.id] = hp; });

// Validierung: alle Protokolle erfasst?
const allAssigned = new Set();
Object.values(MODULE_MAP).forEach(ids => ids.forEach(id => allAssigned.add(id)));
const missing = config.hangingProtocols.filter(hp => !allAssigned.has(hp.id));
const extra = [...allAssigned].filter(id => !byId[id]);

if (missing.length > 0) {
  console.error('FEHLER: Protokolle nicht zugewiesen:');
  missing.forEach(hp => console.error('  ' + hp.id));
  process.exit(1);
}
if (extra.length > 0) {
  console.error('FEHLER: Nicht existierende Protokoll-IDs in Modul-Map:');
  extra.forEach(id => console.error('  ' + id));
  process.exit(1);
}

// Modul-Dateien schreiben
const outDir = path.join(__dirname, 'protocols');
let totalCount = 0;

Object.entries(MODULE_MAP).forEach(([filename, ids]) => {
  const protocols = ids.map(id => byId[id]);
  totalCount += protocols.length;

  const header = `/**
 * ${filename} - Hanging Protocols fuer OHIF v3
 * Automatisch extrahiert aus default.js.
 *
 * Protokolle (${protocols.length}):
${protocols.map(p => ` *   - ${p.id} (${p.name})`).join('\n')}
 */
module.exports = [
`;

  const body = protocols.map(p => '  ' + JSON.stringify(p, null, 2).replace(/\n/g, '\n  ')).join(',\n');

  const footer = '\n];\n';

  const content = header + body + footer;
  const outPath = path.join(outDir, filename);
  fs.writeFileSync(outPath, content);
  console.log(`${filename}: ${protocols.length} Protokolle`);
});

console.log(`\nTotal: ${totalCount} Protokolle in ${Object.keys(MODULE_MAP).length} Modulen`);
console.log('Extraktion abgeschlossen.');
