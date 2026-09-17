/**
 * patch-unsupported-displayset.js
 *
 * Patcht extensions/default/src/commandsModule.ts und
 * extensions/default/src/utils/layerConfigurationUtils.ts:
 *
 * Problem: Wenn eine Studie DisplaySets enthaelt, die als "unsupported"
 * markiert sind (z.B. SR, PDF, ungewoehnliche SC-Bilder), und der User
 * im StudyBrowser auf deren Thumbnail klickt, wird addDisplaySetAsLayer
 * aufgerufen. Die Funktion canAddDisplaySetToViewport prueft nicht auf
 * das `unsupported` Flag, gibt true zurueck, und anschliessend wirft
 * getViewportsRequireUpdate "Unsupported displaySet" -> App-Absturz.
 *
 * Fix:
 * 1. canAddDisplaySetToViewport: Prueft auf displaySet.unsupported
 *    und gibt false zurueck.
 * 2. addDisplaySetAsLayer: Zusätzlicher Guard vor getViewportsRequireUpdate.
 */
const fs = require('fs');
const path = require('path');

// --- Patch 1: canAddDisplaySetToViewport ---
const layerUtilsPath = path.join(
  process.cwd(),
  'extensions/default/src/utils/layerConfigurationUtils.ts'
);

if (!fs.existsSync(layerUtilsPath)) {
  console.error('FEHLER: Datei nicht gefunden:', layerUtilsPath);
  process.exit(1);
}

let layerSrc = fs.readFileSync(layerUtilsPath, 'utf8');

if (layerSrc.includes('patch-unsupported-displayset')) {
  console.log('layerConfigurationUtils.ts: Patch bereits angewendet.');
} else {
  // Patch canAddDisplaySetToViewport: unsupported-Check hinzufuegen
  const oldCanAdd = `  // Check if the display set exists
  const displaySet = displaySetService.getDisplaySetByUID(displaySetInstanceUID);
  if (!displaySet) {
    return false;
  }

  // Get current display sets in the viewport`;

  const newCanAdd = `  // Check if the display set exists
  const displaySet = displaySetService.getDisplaySetByUID(displaySetInstanceUID);
  if (!displaySet) {
    return false;
  }

  // patch-unsupported-displayset: Unsupported DisplaySets nicht als Layer zulassen
  if (displaySet.unsupported) {
    return false;
  }

  // Get current display sets in the viewport`;

  if (layerSrc.includes(oldCanAdd)) {
    layerSrc = layerSrc.replace(oldCanAdd, newCanAdd);
    fs.writeFileSync(layerUtilsPath, layerSrc);
    console.log('layerConfigurationUtils.ts gepatcht: canAddDisplaySetToViewport prueft auf unsupported.');
  } else {
    console.error('FEHLER: Marker in canAddDisplaySetToViewport nicht gefunden.');
    process.exit(1);
  }
}

// --- Patch 2: addDisplaySetAsLayer (zusaetzlicher Guard) ---
const commandsPath = path.join(
  process.cwd(),
  'extensions/default/src/commandsModule.ts'
);

if (!fs.existsSync(commandsPath)) {
  console.error('FEHLER: Datei nicht gefunden:', commandsPath);
  process.exit(1);
}

let cmdSrc = fs.readFileSync(commandsPath, 'utf8');

if (cmdSrc.includes('patch-unsupported-displayset')) {
  console.log('commandsModule.ts: Patch bereits angewendet.');
} else {
  // Patch addDisplaySetAsLayer: unsupported-Check vor getViewportsRequireUpdate
  const oldAddLayer = `      // Get the display set
      const displaySet = displaySetService.getDisplaySetByUID(displaySetInstanceUID);
      if (!displaySet) {
        return;
      }

      // Get current display sets for the viewport`;

  const newAddLayer = `      // Get the display set
      const displaySet = displaySetService.getDisplaySetByUID(displaySetInstanceUID);
      if (!displaySet) {
        return;
      }

      // patch-unsupported-displayset: Unsupported DisplaySets abfangen
      if (displaySet.unsupported) {
        console.warn('addDisplaySetAsLayer: DisplaySet ist als unsupported markiert, ueberspringe.');
        return;
      }

      // Get current display sets for the viewport`;

  if (cmdSrc.includes(oldAddLayer)) {
    cmdSrc = cmdSrc.replace(oldAddLayer, newAddLayer);
    fs.writeFileSync(commandsPath, cmdSrc);
    console.log('commandsModule.ts gepatcht: addDisplaySetAsLayer prueft auf unsupported.');
  } else {
    console.error('FEHLER: Marker in addDisplaySetAsLayer nicht gefunden.');
    process.exit(1);
  }
}

console.log('Patch abgeschlossen: Unsupported-DisplaySet-Absturz behoben.');
