/**
 * patch-encapsulated-pdf-frames.js
 *
 * Patcht zwei Dateien:
 *
 * 1. extensions/dicom-pdf/src/getSopClassHandlerModule.js
 *    Problem: AVIEW/Polaris CAD sendet Encapsulated PDF (SOP Class 1.2.840.10008.5.1.4.1.1.104.1)
 *    mit Modality "CT". OHIF's dicom-pdf Handler setzt numImageFrames:0, aber der
 *    Thumbnail-Prefetcher oder HangingProtocol versucht trotzdem frames/1 zu laden
 *    → 400 Bad Request → "Error: request failed" in der Console.
 *    Fix: unsupported:true zum DisplaySet hinzufuegen, damit Prefetcher und
 *    HangingProtocol diese DisplaySets ignorieren. Das dicom-pdf ViewportModule
 *    prueft nicht auf unsupported — es laedt den PDF direkt via BulkDataURI.
 *
 * 2. node_modules/dicomweb-client/src/api.js
 *    Fix: 400/404 Statuscode bei frame-Requests als "no data" behandeln statt
 *    Error zu werfen. Wird als Fallback gebraucht, falls andere Extensions
 *    trotzdem frame-Requests senden.
 */
const fs = require('fs');
const path = require('path');

// ─── Fix 1: dicom-pdf sopClassHandler — BulkDataURI direkt verwenden ───
const pdfHandlerPath = path.join(
  process.cwd(),
  'extensions/dicom-pdf/src/getSopClassHandlerModule.js'
);

if (fs.existsSync(pdfHandlerPath)) {
  let src = fs.readFileSync(pdfHandlerPath, 'utf8');

  if (src.includes('patch-encapsulated-pdf-frames')) {
    console.log('dicom-pdf: Patch bereits angewendet.');
  } else {
    // Problem: OHIFs getDirectURL() versucht bei EncapsulatedDocument entweder
    // value.retrieveBulkData() (funktioniert nicht, wenn dicomweb-client kein
    // retrieveBulkData anhaengt) oder baut /rendered (Orthanc liefert 400).
    // Orthanc/DICOMweb BulkDataURI fuer 0042,0011 ist jetzt im Backend-Proxy
    // auf /bulk/00420011 umgeschrieben und liefert application/pdf Rohdaten.
    // Fix: renderedUrl direkt auf BulkDataURI setzen, falls vorhanden.
    const oldPattern = /const renderedUrl = dataSource\.retrieve\.directURL\(\{[\s\S]*?singlepart: ['"]pdf['"],?\s*\}\);/;
    const newPattern = `const encapsulatedDocument = instance.EncapsulatedDocument;
  const renderedUrl = (encapsulatedDocument && encapsulatedDocument.BulkDataURI)
    ? encapsulatedDocument.BulkDataURI
    : dataSource.retrieve.directURL({
        instance,
        tag: 'EncapsulatedDocument',
        defaultType: MIMETypeOfEncapsulatedDocument || 'application/pdf',
        singlepart: 'pdf',
      }); // patch-encapsulated-pdf-frames`;

    if (src.match(oldPattern)) {
      src = src.replace(oldPattern, newPattern);
    } else {
      console.warn('WARN: Konnte renderedUrl-Zeile nicht patchen, versuche alternativen Marker.');
      // Sicherer Fallback: Suche die Variable 'renderedUrl' und ersetze den
      // direkten directURL-Aufruf durch einen ternaeren BulkDataURI-Check.
      const altPattern = /renderedUrl:\s*dataSource\.retrieve\.directURL\(\{[\s\S]*?singlepart:\s*['"]pdf['"],?\s*\}\),/;
      const altNew = `renderedUrl: (instance.EncapsulatedDocument && instance.EncapsulatedDocument.BulkDataURI)
      ? instance.EncapsulatedDocument.BulkDataURI
      : dataSource.retrieve.directURL({
          instance,
          tag: 'EncapsulatedDocument',
          defaultType: MIMETypeOfEncapsulatedDocument || 'application/pdf',
          singlepart: 'pdf',
        }), // patch-encapsulated-pdf-frames`;
      if (src.match(altPattern)) {
        src = src.replace(altPattern, altNew);
      } else {
        console.error('FEHLER: renderedUrl-Aufruf nicht gefunden in dicom-pdf.');
        process.exit(1);
      }
    }

    // numImageFrames:0 bleibt; kein unsupported:true mehr, damit der
    // dicom-pdf Viewport das DisplaySet oeffnen kann. Thumbnail-Prefetch
    // und HangingProtocol koennen frames/1 senden, dicomweb-client Patch
    // behandelt 400 fuer Encapsulated PDF (keine Pixel-Daten).
    const numImagePattern = /numImageFrames:\s*0,/;
    if (!src.match(numImagePattern)) {
      console.error('FEHLER: numImageFrames:0 nicht gefunden in dicom-pdf.');
      process.exit(1);
    }

    fs.writeFileSync(pdfHandlerPath, src);
    console.log('dicom-pdf/src/getSopClassHandlerModule.js gepatcht: renderedUrl verwendet BulkDataURI, kein unsupported.');
  }
} else {
  console.error('FEHLER: extensions/dicom-pdf/src/getSopClassHandlerModule.js nicht gefunden.');
  process.exit(1);
}

// ─── Fix 2: dicomweb-client — 400/404 bei frames als "no data" ───
const dicomwebClientPath = path.join(
  process.cwd(),
  'node_modules/dicomweb-client/src/api.js'
);

if (fs.existsSync(dicomwebClientPath)) {
  let src = fs.readFileSync(dicomwebClientPath, 'utf8');

  if (src.includes('patch-encapsulated-pdf-frames')) {
    console.log('dicomweb-client: Patch bereits angewendet.');
  } else {
    // Patch: 400 bei frames/1 = no frames (z.B. Encapsulated PDF)
    // Der originale Code wirft bei status >= 400 einen Error.
    // Wir fuegen eine Ausnahme fuer 400 bei frame-Requests hinzu.
    const oldPattern = `          } else {
            const error = new Error('request failed');
            error.request = request;
            error.response = request.response;
            error.status = request.status;
            if (this.verbose) {
              console.error('request failed: ', request);
              console.error(error);
              console.error(error.response);
            }

            errorInterceptor(error);

            reject(error);
          }`;

    const newPattern = `          } else if (request.status === 400 && request.responseURL && request.responseURL.includes('/frames/')) {
            // patch-encapsulated-pdf-frames: 400 bei frames/1 = no frames
            // (z.B. Encapsulated PDF mit Modality "CT" von AVIEW/Polaris CAD)
            if (this.verbose) {
              console.warn('No frames available for this instance (likely Encapsulated PDF): ', request.responseURL);
            }
            resolve([]);
          } else {
            const error = new Error('request failed');
            error.request = request;
            error.response = request.response;
            error.status = request.status;
            if (this.verbose) {
              console.error('request failed: ', request);
              console.error(error);
              console.error(error.response);
            }

            errorInterceptor(error);

            reject(error);
          }`;

    if (src.includes(oldPattern)) {
      src = src.replace(oldPattern, newPattern);
      fs.writeFileSync(dicomwebClientPath, src);
      console.log('dicomweb-client/src/api.js gepatcht: 400 bei frames/1 wird als "no data" behandelt.');
    } else {
      console.warn('WARN: exaktes Pattern in api.js nicht gefunden — versuche vereinfachten Patch.');
      // Vereinfachter Patch: Suche nur nach der throw-Zeile
      const simpleOld = `const error = new Error('request failed');`;
      const simpleNew = `// patch-encapsulated-pdf-frames: 400 bei frames/ = no frames (Encapsulated PDF)
          if (request.status === 400 && request.responseURL && request.responseURL.includes('/frames/')) {
            if (this.verbose) {
              console.warn('No frames available (likely Encapsulated PDF): ', request.responseURL);
            }
            resolve([]);
            return;
          }
          const error = new Error('request failed');`;
      if (src.includes(simpleOld)) {
        src = src.replace(simpleOld, simpleNew);
        fs.writeFileSync(dicomwebClientPath, src);
        console.log('dicomweb-client/src/api.js gepatcht (vereinfacht): 400 bei frames/ wird als "no data" behandelt.');
      } else {
        console.error('FEHLER: Konnte dicomweb-client nicht patchen.');
      }
    }
  }
} else {
  console.warn('WARN: node_modules/dicomweb-client/src/api.js nicht gefunden — Fix 2 uebersprungen.');
}

console.log('Patch abgeschlossen: Encapsulated PDF verwendet BulkDataURI direkt, frames/1 400 wird toleriert.');
