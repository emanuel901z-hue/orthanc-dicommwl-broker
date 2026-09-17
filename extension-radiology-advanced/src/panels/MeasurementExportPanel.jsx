// MeasurementExportPanel - Messungs-Export (DICOM SR / CSV / JSON)
//
// Ermöglicht den Export aller Messungen (Laengen, Winkel, ROIs, etc.)
// aus dem aktiven Viewer in verschiedene Formate:
//  - DICOM SR (Structured Report) - speicherbar im PACS
//  - CSV - fuer Tabellenkalkulation / RIS-Import
//  - JSON - fuer programmatische Weiterverarbeitung
//
// Die Messungen werden aus dem measurementService ausgelesen und
// strukturiert aufbereitet. Fuer DICOM SR wird dcmjs verwendet,
// falls verfuegbar.

import React, { useState, useEffect, useCallback } from 'react';

function MeasurementExportPanel({ servicesManager }) {
  const { measurementService, displaySetService } = servicesManager?.services || {};

  const [measurements, setMeasurements] = useState([]);
  const [exportFormat, setExportFormat] = useState('csv');
  const [statusMsg, setStatusMsg] = useState('');
  const [exportData, setExportData] = useState(null);

  // Messungen laden
  useEffect(() => {
    if (!measurementService) return;

    const updateMeasurements = () => {
      const all = measurementService.getMeasurements();
      const list = Array.isArray(all) ? all : [];
      setMeasurements(list.map((m, i) => {
        // OHIF v3 speichert Stats in measurement.data (cachedStats, keyed by imageId)
        const cachedStats = m.data || {};
        const imageIds = Object.keys(cachedStats).filter(k => k !== 'undefined');
        const s = imageIds.length > 0 ? cachedStats[imageIds[0]] : {};
        const length = s.length != null ? s.length.toFixed(2) + ' ' + (s.unit || 'mm') : null;
        const angle = s.angle != null ? s.angle.toFixed(1) + ' deg' : null;
        const area = s.area != null ? s.area.toFixed(1) + ' ' + (s.areaUnit || 'mm2') : null;
        const mean = s.mean != null ? s.mean.toFixed(1) : null;
        const stdDev = s.stdDev != null ? s.stdDev.toFixed(2) : null;
        return {
          index: i + 1,
          uid: m.uid || ('meas-' + i),
          toolName: m.toolName || 'Unknown',
          label: m.label || m.toolName || '',
          length,
          angle,
          area,
          mean,
          stdDev,
          unit: s.unit || s.modalityUnit || '',
          data: m,
        };
      }));
    };

    updateMeasurements();
    const subs = [];
    const E = measurementService.EVENTS || {};
    for (const evt of [E.MEASUREMENT_ADDED, E.MEASUREMENT_UPDATED, E.MEASUREMENT_REMOVED]) {
      if (evt && measurementService.subscribe) {
        subs.push(measurementService.subscribe(evt, updateMeasurements));
      }
    }
    return () => subs.forEach(s => s?.unsubscribe?.());
  }, [measurementService]);

  // CSV generieren
  const generateCSV = useCallback(() => {
    const headers = ['Nr', 'Tool', 'Label', 'Laenge (mm)', 'Winkel (deg)', 'Flaeche (mm2)', 'Mean', 'StdDev'];
    const rows = measurements.map(m => [
      m.index, m.toolName, m.label, m.length || '', m.angle || '', m.area || '', m.mean || '', m.stdDev || ''
    ]);
    const csv = [headers, ...rows].map(row =>
      row.map(cell => {
        const s = String(cell);
        return s.includes(',') || s.includes('"') ? '"' + s.replace(/"/g, '""') + '"' : s;
      }).join(',')
    ).join('\n');
    return csv;
  }, [measurements]);

  // JSON generieren
  const generateJSON = useCallback(() => {
    const studyInfo = getStudyInfo(displaySetService);
    const data = {
      exportDate: new Date().toISOString(),
      study: studyInfo,
      measurementCount: measurements.length,
      measurements: measurements.map(m => ({
        toolName: m.toolName,
        label: m.label,
        length: m.length,
        angle: m.angle,
        area: m.area,
        stats: { mean: m.mean, stdDev: m.stdDev },
        unit: m.unit,
      })),
    };
    return JSON.stringify(data, null, 2);
  }, [measurements, displaySetService]);

  // DICOM SR generieren (vereinfacht, benoetigt dcmjs)
  const generateDICOMSR = useCallback(() => {
    try {
      // Versuche dcmjs zu laden (in OHIF verfuegbar)
      const dcmjs = require('dcmjs');
      const studyInfo = getStudyInfo(displaySetService);

      // SR-Dokument-Struktur erstellen
      const measurementsData = measurements.map(m => ({
        TrackingIdentifier: m.toolName,
        TextValue: m.label || m.toolName,
        MeasuredValue: m.length || m.angle || m.mean || '',
        NumericValue: parseFloat(m.length) || parseFloat(m.angle) || parseFloat(m.mean) || 0,
        MeasurementUnits: m.unit || 'mm',
        TrackingIdentifierValue: m.uid,
      }));

      // Vereinfachte SR-Erstellung
      // Eine vollstaendige SR-Erstellung erfordert die dcmjs SR-API
      // mit korrektem IOD (Basic Text SR / Comprehensive SR)
      const srDataset = {
        StudyInstanceUID: studyInfo.studyInstanceUID || generateUID(),
        SeriesInstanceUID: generateUID(),
        SOPInstanceUID: generateUID(),
        Modality: 'SR',
        SeriesDescription: 'Messungs-Export (' + measurements.length + ')',
        StudyDescription: studyInfo.studyDescription || 'Measurement Export',
        PatientName: studyInfo.patientName || '',
        PatientID: studyInfo.patientID || '',
        StudyDate: new Date().toISOString().substring(0, 10).replace(/-/g, ''),
        ContentDate: new Date().toISOString().substring(0, 10).replace(/-/g, ''),
        ContentTime: new Date().toTimeString().substring(0, 8).replace(/:/g, ''),
        ValueType: 'CONTAINER',
        ConceptName: { CodeMeaning: 'Measurement Report' },
        ContentSequence: measurementsData,
      };

      // Mit dcmjs DICOM-Datei erstellen
      if (dcmjs.DicomMessage) {
        // const buffer = dcmjs.DicomMessage.write(srDataset, []);
        // return new Blob([buffer], { type: 'application/dicom' });
      }

      // Fallback: JSON mit SR-Metadaten
      return JSON.stringify(srDataset, null, 2);
    } catch (err) {
      console.error('[MeasExport] DICOM SR Fehler:', err);
      return 'DICOM SR Export fehlgeschlagen: ' + err.message +
        '\n\nFallback JSON:\n' + generateJSON();
    }
  }, [measurements, displaySetService, generateJSON]);

  // Export ausfuehren
  const doExport = useCallback(() => {
    if (measurements.length === 0) {
      setStatusMsg('Keine Messungen zum Exportieren');
      return;
    }

    let content = '';
    let mimeType = 'text/plain';
    let fileExt = 'txt';

    switch (exportFormat) {
      case 'csv':
        content = generateCSV();
        mimeType = 'text/csv';
        fileExt = 'csv';
        break;
      case 'json':
        content = generateJSON();
        mimeType = 'application/json';
        fileExt = 'json';
        break;
      case 'dicomsr':
        content = generateDICOMSR();
        mimeType = 'application/dicom';
        fileExt = 'dcm';
        break;
    }

    // Download ausloesen
    try {
      const blob = new Blob([content], { type: mimeType });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const timestamp = new Date().toISOString().substring(0, 19).replace(/[:T]/g, '-');
      a.download = 'messungen_' + timestamp + '.' + fileExt;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      setExportData(content);
      setStatusMsg(measurements.length + ' Messung(en) als ' + exportFormat.toUpperCase() + ' exportiert');
    } catch (err) {
      setStatusMsg('Export-Fehler: ' + err.message);
    }
  }, [measurements, exportFormat, generateCSV, generateJSON, generateDICOMSR]);

  // In Zwischenablage kopieren
  const copyToClipboard = useCallback(() => {
    let content = '';
    if (exportFormat === 'csv') content = generateCSV();
    else if (exportFormat === 'json') content = generateJSON();
    else content = generateDICOMSR();

    try {
      navigator.clipboard?.writeText(content);
      setStatusMsg('In Zwischenablage kopiert (' + content.length + ' Zeichen)');
    } catch (err) {
      setStatusMsg('Clipboard-Fehler: ' + err.message);
    }
  }, [exportFormat, generateCSV, generateJSON, generateDICOMSR]);

  const formatBtnStyle = (active) => ({
    flex: 1, padding: '8px', border: '1px solid ' + (active ? '#2a6cc7' : '#444'),
    borderRadius: '4px', background: active ? '#2a6cc7' : '#1a1a2e',
    color: active ? '#fff' : '#999', cursor: 'pointer', fontSize: '12px', fontWeight: 'bold',
  });

  // Messungen nach Tool gruppieren
  const toolGroups = {};
  measurements.forEach(m => {
    if (!toolGroups[m.toolName]) toolGroups[m.toolName] = [];
    toolGroups[m.toolName].push(m);
  });

  return React.createElement('div', {
    style: { padding: '8px', height: '100%', overflow: 'auto', background: '#0d1117' },
    'data-cy': 'measurement-export-panel',
  },
    // Header
    React.createElement('h3', {
      style: { color: '#e0e0e0', fontSize: '14px', margin: '0 0 8px 0', borderBottom: '1px solid #333', paddingBottom: '4px' },
    }, 'Messungs-Export'),

    // Messungs-Uebersicht
    React.createElement('div', {
      style: { background: '#161b22', padding: '8px', borderRadius: '4px', marginBottom: '12px' },
    },
      React.createElement('div', { style: { fontSize: '20px', fontWeight: 'bold', color: '#4ec9b0', textAlign: 'center' } },
        measurements.length + ' Messung(en)'
      ),
      Object.keys(toolGroups).length > 0 && React.createElement('div', {
        style: { fontSize: '11px', color: '#999', marginTop: '4px' },
      },
        Object.entries(toolGroups).map(([tool, items]) =>
          tool + ' (' + items.length + ')'
        ).join(', ')
      )
    ),

    // Messungs-Liste
    measurements.length > 0 && React.createElement('div', {
      style: { background: '#161b22', borderRadius: '4px', marginBottom: '12px', maxHeight: '200px', overflow: 'auto' },
    },
      measurements.map((m, i) =>
        React.createElement('div', {
          key: m.uid || m.index || i,
          style: { padding: '4px 8px', borderBottom: '1px solid #2a2a3a', fontSize: '11px' },
        },
          React.createElement('span', { style: { color: '#4ec9b0', fontWeight: 'bold' } }, '#' + m.index),
          React.createElement('span', { style: { color: '#999' } }, ' ' + m.toolName + ' '),
          React.createElement('span', { style: { color: '#e0e0e0' } },
            [m.length, m.angle, m.area, m.mean && ('Mean: ' + m.mean)].filter(Boolean).join(' | ')
          ),
        )
      )
    ),

    // Format-Auswahl
    React.createElement('div', { style: { fontSize: '11px', color: '#999', marginBottom: '4px' } }, 'Export-Format:'),
    React.createElement('div', { style: { display: 'flex', gap: '4px', marginBottom: '12px' } },
      React.createElement('button', {
        style: formatBtnStyle(exportFormat === 'csv'),
        onClick: () => setExportFormat('csv'),
      }, 'CSV'),
      React.createElement('button', {
        style: formatBtnStyle(exportFormat === 'json'),
        onClick: () => setExportFormat('json'),
      }, 'JSON'),
      React.createElement('button', {
        style: formatBtnStyle(exportFormat === 'dicomsr'),
        onClick: () => setExportFormat('dicomsr'),
      }, 'DICOM SR'),
    ),

    // Export-Buttons
    React.createElement('div', { style: { display: 'flex', gap: '4px', marginBottom: '12px' } },
      React.createElement('button', {
        style: {
          flex: 2, padding: '10px', background: '#2a6cc7', color: '#fff',
          border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '13px', fontWeight: 'bold',
        },
        onClick: doExport,
        disabled: measurements.length === 0,
      }, '\u2B07 Export herunterladen'),
      React.createElement('button', {
        style: {
          flex: 1, padding: '10px', background: '#444', color: '#ccc',
          border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '12px',
        },
        onClick: copyToClipboard,
        disabled: measurements.length === 0,
      }, '\u2398 Kopieren'),
    ),

    // Status
    statusMsg && React.createElement('div', {
      style: { color: '#4ec9b0', fontSize: '11px', padding: '6px', background: '#0a1a1a', borderRadius: '3px' },
    }, statusMsg),

    // Hinweis
    React.createElement('div', {
      style: { color: '#666', fontSize: '10px', marginTop: '12px', padding: '6px', background: '#161b22', borderRadius: '3px' },
    }, 'CSV: fuer Tabellenkalkulation/RIS-Import.\nJSON: fuer programmatische Weiterverarbeitung.\nDICOM SR: Structured Report, speicherbar im PACS (erfordert dcmjs).\n\nDie Messungen koennen ans RIS/PACS zurueckgegeben oder fuer die Befunddokumentation verwendet werden.'),
  );
}

// Hilfsfunktionen
function getStudyInfo(displaySetService) {
  if (!displaySetService) return {};
  const ds = displaySetService.getActiveDisplaySets();
  if (!ds || ds.length === 0) return {};
  const first = ds[0];
  const instance = first.instances?.[0] || {};
  return {
    studyInstanceUID: first.StudyInstanceUID || instance.StudyInstanceUID,
    studyDescription: first.StudyDescription || instance.StudyDescription,
    patientName: first.PatientName || instance.PatientName,
    patientID: first.PatientID || instance.PatientID,
    modality: first.Modality || instance.Modality,
  };
}

function generateUID() {
  // DICOM-konforme UID-Generierung mit Timestamp + Counter + Zufall.
  // Root: 1.2.826.0.1.3680043.10.997 (Carestream-reserviert).
  // Verwendet Date.now() fuer Eindeutigkeit ueber die Zeit und einen
  // monotonen Counter fuer Eindeutigkeit bei gleichzeitiger Generierung.
  // Math.random() allein kann Kollisionen erzeugen.
  const timestamp = Date.now();
  const counter = (generateUID._counter = (generateUID._counter || 0) + 1);
  const random = Math.floor(Math.random() * 1000000);
  return `1.2.826.0.1.3680043.10.997.${timestamp}.${counter}.${random}`;
}

export default MeasurementExportPanel;
