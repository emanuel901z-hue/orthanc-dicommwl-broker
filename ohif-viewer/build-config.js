/**
 * build-config.js - Assembler fuer OHIF app-config (default.js)
 *
 * Liest:
 *   - ohif-viewer/static-config.js  (statische Config: Server, dataSources, etc.)
 *   - ohif-viewer/protocols/*.js    (modulare Hanging Protocols)
 *
 * Schreibt:
 *   - ohif-viewer/default.js        (finale, von OHIF geladene Config)
 *
 * Usage: node ohif-viewer/build-config.js
 *
 * Im Dockerfile wird dieses Script vor dem COPY von default.js
 * ausgefuehrt, sodass die generierte Datei in den Build einfliest.
 */
const fs = require('fs');
const path = require('path');

const DIR = __dirname;
const PROTOCOLS_DIR = path.join(DIR, 'protocols');
const OUTPUT_FILE = path.join(DIR, 'default.js');

// --- Statische Config laden ---
const staticConfig = require(path.join(DIR, 'static-config.js'));

// --- Protokoll-Module in definierter Reihenfolge laden ---
const MODULE_FILES = [
  'generic.js',
  'lung-screening.js',
];

const allProtocols = [];
const loadedModules = [];

MODULE_FILES.forEach(file => {
  const modPath = path.join(PROTOCOLS_DIR, file);
  if (!fs.existsSync(modPath)) {
    console.error(`FEHLER: Modul nicht gefunden: ${modPath}`);
    process.exit(1);
  }
  const protocols = require(modPath);
  if (!Array.isArray(protocols)) {
    console.error(`FEHLER: ${file} exportiert kein Array`);
    process.exit(1);
  }
  loadedModules.push({ file, count: protocols.length });
  allProtocols.push(...protocols);
});

// --- Validierung ---

// Duplikat-Pruefung
const seen = new Set();
const duplicates = [];
allProtocols.forEach(hp => {
  if (seen.has(hp.id)) duplicates.push(hp.id);
  seen.add(hp.id);
});
if (duplicates.length > 0) {
  console.error('FEHLER: Duplikate gefunden: ' + duplicates.join(', '));
  process.exit(1);
}

// Referenzintegritaet: jede displaySet ID muss in displaySetSelectors existieren
let refErrors = 0;
allProtocols.forEach(hp => {
  const dssKeys = Object.keys(hp.displaySetSelectors);
  if (Array.isArray(hp.displaySetSelectors)) {
    console.error(`FEHLER: ${hp.id} - displaySetSelectors ist Array, nicht Object`);
    refErrors++;
  }
  hp.stages.forEach(stage => {
    stage.viewports.forEach((vp, vi) => {
      vp.displaySets.forEach(ds => {
        if (!dssKeys.includes(ds.id)) {
          console.error(`FEHLER: ${hp.id} VP ${vi} referenziert unbekannte ID: ${ds.id}`);
          refErrors++;
        }
      });
    });
  });
});
if (refErrors > 0) process.exit(1);

// --- Hotkeys (unveraendert aus der Original-Datei) ---
const HOTKEYS = [
  { command: 'incrementActiveViewport', label: 'Next Viewport', keys: ['right'] },
  { command: 'decrementActiveViewport', label: 'Previous Viewport', keys: ['left'] },
  { command: 'rotateViewportCW', label: 'Rotate Right', keys: ['r'] },
  { command: 'flipViewportHorizontal', label: 'Flip H', keys: ['h'] },
  { command: 'invertViewport', label: 'Invert', keys: ['i'] },
];

// --- Finale Config zusammenstellen ---
const finalConfig = {
  ...staticConfig,
  hangingProtocols: allProtocols,
  defaultHangingProtocolName: 'ct-default',
  hotkeys: HOTKEYS,
};

// --- default.js schreiben ---
const output = `// ============================================================================
// OHIF v3 App-Konfiguration (default.js)
// ============================================================================
// Diese Datei wurde automatisch von build-config.js assembliert.
// NICHT MANUELL BEARBETEN - Aenderungen an den Modulen in protocols/ bzw.
// an static-config.js vornehmen und build-config.js neu ausfuehren.
//
// Module:
${loadedModules.map(m => `//   - ${m.file} (${m.count} Protokolle)`).join('\n')}
// Gesamt: ${allProtocols.length} Hanging Protocols
// ============================================================================

window.config = ${JSON.stringify(finalConfig, null, 2)};
`;

fs.writeFileSync(OUTPUT_FILE, output);

console.log(`build-config.js: ${allProtocols.length} Protokolle assembliert`);
console.log('Module:');
loadedModules.forEach(m => console.log(`  ${m.file}: ${m.count}`));
console.log(`Output: ${OUTPUT_FILE} (${output.length} bytes, ${output.split('\n').length} lines)`);
console.log('Assemblierung abgeschlossen.');
