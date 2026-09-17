/**
 * patch-dynamic-volume.js
 *
 * Patcht extensions/default/src/getSopClassHandlerModule.js:
 *
 * Problem: Der stack sopClassHandler ruft fuer jede Serie mehrere Funktionen
 * auf, die alle DICOM-Metadaten zugreifen (PixelSpacing, ImagePositionPatient,
 * ImageOrientationPatient). Wenn diese fehlen (z.B. bei SC-Bildern von
 * Carestream/AVIEW), stuerzen folgende Funktionen ab:
 * - getDynamicVolumeInfo -> csGetDynamicVolumeInfo -> splitImageIdsBy4DTags
 * - getDisplaySetInfo -> isDisplaySetReconstructable -> sortInstancesByPosition
 * - makeDisplaySet -> getDisplaySetMessages -> sortInstancesByPosition
 *   -> vec3.subtract auf undefined ImagePositionPatient
 *
 * Fix: Drei try-catch-Blöcke:
 * 1. getDynamicVolumeInfo: try-catch um csGetDynamicVolumeInfo
 * 2. getDisplaySetInfo: try-catch um gesamten Funktionskoerper
 * 3. makeDisplaySet: try-catch um getDisplaySetMessages-Aufruf
 */
const fs = require('fs');
const path = require('path');

const targetPath = path.join(
  process.cwd(),
  'extensions/default/src/getSopClassHandlerModule.js'
);

if (!fs.existsSync(targetPath)) {
  console.error('FEHLER: Datei nicht gefunden:', targetPath);
  process.exit(1);
}

let src = fs.readFileSync(targetPath, 'utf8');
let patched = false;

// --- Patch 1: getDynamicVolumeInfo try-catch ---
if (src.includes('patch-dynamic-volume-v1')) {
  console.log('getSopClassHandlerModule.js: Patch 1 (getDynamicVolumeInfo) bereits angewendet.');
} else {
  const oldCode1 = `  const { getDynamicVolumeInfo: csGetDynamicVolumeInfo } = volumeLoaderUtility.exports;

  return csGetDynamicVolumeInfo(imageIds);`;

  const newCode1 = `  const { getDynamicVolumeInfo: csGetDynamicVolumeInfo } = volumeLoaderUtility.exports;

  // patch-dynamic-volume-v1: try-catch fuer unvollstaendige Metadaten
  try {
    return csGetDynamicVolumeInfo(imageIds);
  } catch (e) {
    console.warn('getDynamicVolumeInfo: Fallback auf nicht-dynamisch:', e?.message || e);
    return { isDynamicVolume: false, timePoints: [imageIds], splittingTag: null };
  }`;

  if (src.includes(oldCode1)) {
    src = src.replace(oldCode1, newCode1);
    patched = true;
    console.log('getSopClassHandlerModule.js: Patch 1 (getDynamicVolumeInfo try-catch) angewendet.');
  } else {
    console.error('FEHLER: Marker fuer Patch 1 nicht gefunden.');
    process.exit(1);
  }
}

// --- Patch 2: getDisplaySetInfo try-catch ---
if (src.includes('patch-dynamic-volume-v2')) {
  console.log('getSopClassHandlerModule.js: Patch 2 (getDisplaySetInfo) bereits angewendet.');
} else {
  const oldCode2 = `function getDisplaySetInfo(instances) {
  const dynamicVolumeInfo = getDynamicVolumeInfo(instances);
  const { isDynamicVolume, timePoints } = dynamicVolumeInfo;
  let displaySetInfo;

  const { appConfig } = appContext;

  if (isDynamicVolume) {
    const timePoint = timePoints[0];
    const instancesMap = new Map();

    let firstTimePointInstances;

    if (instances[0].NumberOfFrames > 1 && timePoints.length > 1) {
      // handle multiframe dynamic volume
      firstTimePointInstances = timePoints[0].map(imageId => metaData.get('instance', imageId));
    } else {
      // O(n) to convert it into a map and O(1) to find each instance
      instances.forEach(instance => instancesMap.set(instance.imageId, instance));
      firstTimePointInstances = timePoint.map(imageId => instancesMap.get(imageId));
    }
    displaySetInfo = isDisplaySetReconstructable(firstTimePointInstances, appConfig);
  } else {
    displaySetInfo = isDisplaySetReconstructable(instances, appConfig);
  }

  return {
    isDynamicVolume,
    ...displaySetInfo,
    dynamicVolumeInfo,
  };
}`;

  const newCode2 = `function getDisplaySetInfo(instances) {
  // patch-dynamic-volume-v2: try-catch um gesamten Funktionskoerper.
  try {
    const dynamicVolumeInfo = getDynamicVolumeInfo(instances);
    const { isDynamicVolume, timePoints } = dynamicVolumeInfo;
    let displaySetInfo;

    const { appConfig } = appContext;

    if (isDynamicVolume) {
      const timePoint = timePoints[0];
      const instancesMap = new Map();

      let firstTimePointInstances;

      if (instances[0].NumberOfFrames > 1 && timePoints.length > 1) {
        // handle multiframe dynamic volume
        firstTimePointInstances = timePoints[0].map(imageId => metaData.get('instance', imageId));
      } else {
        // O(n) to convert it into a map and O(1) to find each instance
        instances.forEach(instance => instancesMap.set(instance.imageId, instance));
        firstTimePointInstances = timePoint.map(imageId => instancesMap.get(imageId));
      }
      displaySetInfo = isDisplaySetReconstructable(firstTimePointInstances, appConfig);
    } else {
      displaySetInfo = isDisplaySetReconstructable(instances, appConfig);
    }

    return {
      isDynamicVolume,
      ...displaySetInfo,
      dynamicVolumeInfo,
    };
  } catch (e) {
    console.warn('getDisplaySetInfo: Fallback auf nicht-reconstructable:', e?.message || e);
    return {
      isDynamicVolume: false,
      value: false,
      averageSpacingBetweenFrames: null,
      dynamicVolumeInfo: { isDynamicVolume: false, timePoints: null, splittingTag: null },
    };
  }
}`;

  if (src.includes(oldCode2)) {
    src = src.replace(oldCode2, newCode2);
    patched = true;
    console.log('getSopClassHandlerModule.js: Patch 2 (getDisplaySetInfo try-catch) angewendet.');
  } else {
    console.error('FEHLER: Marker fuer Patch 2 nicht gefunden.');
    process.exit(1);
  }
}

// --- Patch 3: makeDisplaySet try-catch um getDisplaySetMessages ---
// getDisplaySetMessages ruft sortInstancesByPosition, das vec3.subtract
// auf ImagePositionPatient ausfuehrt. Wenn ImagePositionPatient fehlt,
// crasht vec3.subtract mit "Cannot read properties of undefined".
if (src.includes('patch-dynamic-volume-v3')) {
  console.log('getSopClassHandlerModule.js: Patch 3 (makeDisplaySet) bereits angewendet.');
} else {
  const oldCode3 = `  // set appropriate attributes to image set...
  const messages = getDisplaySetMessages(instances, isReconstructable, isDynamicVolume);`;

  const newCode3 = `  // set appropriate attributes to image set...
  // patch-dynamic-volume-v3: try-catch um getDisplaySetMessages
  let messages;
  try {
    messages = getDisplaySetMessages(instances, isReconstructable, isDynamicVolume);
  } catch (e) {
    console.warn('getDisplaySetMessages: Fallback auf leere Messages:', e?.message || e);
    // DisplaySetMessageList-kompatibles Objekt mit size(), includesMessage(), includesAllMessages()
    messages = { messages: [], size: () => 0, includesMessage: () => false, includesAllMessages: () => false };
  }`;

  if (src.includes(oldCode3)) {
    src = src.replace(oldCode3, newCode3);
    patched = true;
    console.log('getSopClassHandlerModule.js: Patch 3 (makeDisplaySet getDisplaySetMessages try-catch) angewendet.');
  } else {
    console.error('FEHLER: Marker fuer Patch 3 nicht gefunden.');
    process.exit(1);
  }
}

if (patched) {
  fs.writeFileSync(targetPath, src);
}

console.log('Patch abgeschlossen: Dynamic-Volume/Metadata-Absturz behoben.');
