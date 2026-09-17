// Quick check script to verify mode patches were applied.
// Gibt Exit-Code 1 zurueck wenn kritische Patches fehlen, damit der
// Docker-Build fehlschlaegt statt stillschweigend inkorrekt zu bauen.
const fs = require('fs');

const basicPath = 'modes/basic/src/index.tsx';
const longPath = 'modes/longitudinal/src/index.ts';

let hasErrors = false;

for (const [name, path] of [['basic', basicPath], ['longitudinal', longPath]]) {
  if (!fs.existsSync(path)) {
    console.error(`[${name}] FEHLER: Datei nicht gefunden: ${path}`);
    hasErrors = true;
    continue;
  }
  const src = fs.readFileSync(path, 'utf8');
  const hasExt = src.includes('@ohif/extension-radiology-advanced');
  const hasRadAdv = src.includes('radAdv');
  const hasRightPanels = src.includes('extension-radiology-advanced.panelModule');
  const hasRightPanelClosed = src.includes('rightPanelClosed: false');

  // Count panel module references
  const panelMatches = src.match(/extension-radiology-advanced\.panelModule\.\w+/g) || [];

  console.log(`[${name}] extension-radiology-advanced: ${hasExt}`);
  console.log(`[${name}] radAdv constant: ${hasRadAdv}`);
  console.log(`[${name}] panelModule refs in rightPanels: ${hasRightPanels}`);
  console.log(`[${name}] panelModule count: ${panelMatches.length}`);
  console.log(`[${name}] panels: ${panelMatches.join(', ')}`);
  console.log(`[${name}] rightPanelClosed: false: ${hasRightPanelClosed}`);

  // Kritische Checks: extension und panels muessen vorhanden sein.
  if (!hasExt) {
    console.error(`[${name}] FEHLER: extension-radiology-advanced nicht in Mode gefunden!`);
    hasErrors = true;
  }
  if (!hasRightPanels) {
    console.error(`[${name}] FEHLER: panelModule-Referenzen in rightPanels fehlen!`);
    hasErrors = true;
  }

  // Show rightPanels line
  const rpMatch = src.match(/rightPanels:\s*\[[^\]]+\]/);
  if (rpMatch) {
    console.log(`[${name}] rightPanels: ${rpMatch[0].substring(0, 200)}...`);
  } else {
    console.error(`[${name}] FEHLER: rightPanels nicht gefunden!`);
    hasErrors = true;
  }
  console.log('---');
}

if (hasErrors) {
  console.error('PATCH-VERIFIKATION FEHLGESCHLAGEN: Kritische Patches fehlen!');
  process.exit(1);
} else {
  console.log('PATCH-VERIFIKATION OK: Alle kritischen Patches angewendet.');
}
