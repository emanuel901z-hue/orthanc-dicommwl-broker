// ROIStatsPanel - ROI-Statistiken und HU/Signal-Intensity-Auslesung
//
// Zeigt:
//  1. Live-Dichtewert (HU bei CT, Signal-Intensity bei MR) an der
//     Cursor-Position im aktiven Viewport
//  2. Statistiken (Mean, Min, Max, StdDev, Flaeche) aller aktiven
//     ROI-Annotationen (RectangleROI, EllipticalROI, CircleROI)
//
// Voraussetzung: ROI-Annotationen werden mit den Standard-Tools
// (RectangleROITool, EllipticalROITool, CircleROI) erstellt.

import React, { useState, useEffect, useCallback, useRef } from 'react';

function ROIStatsPanel({ servicesManager, commandsManager }) {
  const { cornerstoneViewportService, measurementService, displaySetService } =
    servicesManager?.services || {};

  const [cursorValue, setCursorValue] = useState(null);
  const [roiStats, setRoiStats] = useState([]);
  const [activeModality, setActiveModality] = useState('CT');
  const cursorValueRef = useRef(null);
  const activeModalityRef = useRef('CT');

  // updateMeasurements als useCallback im Component-Scope definieren,
  // damit der Refresh-Button (onClick) darauf zugreifen kann.
  const updateMeasurements = useCallback(() => {
    if (!measurementService) return;
    const allMeasurements = measurementService.getMeasurements();
    const rois = Array.isArray(allMeasurements)
      ? allMeasurements.filter(m =>
          m.toolName === 'RectangleROI' ||
          m.toolName === 'EllipticalROI' ||
          m.toolName === 'CircleROI' ||
          m.toolName === 'RectangleROIStartEnd' ||
          m.toolName === 'EllipticalROIStartEnd'
        )
      : [];

    const stats = rois.map((roi, i) => {
      const cachedStats = roi.data || {};
      const imageIds = Object.keys(cachedStats).filter(k => k !== 'undefined');
      const s = imageIds.length > 0 ? cachedStats[imageIds[0]] : {};
      const curModality = activeModalityRef.current;
      const unit = (s.Modality === 'CT' || (curModality === 'CT' && !s.Modality)) ? ' HU' : '';
      const areaUnit = s.areaUnit || 'mm²';
      let dtMean = null, dtMax = null;
      if (roi.displayText) {
        try {
          const dt = typeof roi.displayText === 'string' ? JSON.parse(roi.displayText) : roi.displayText;
          if (dt.primary && Array.isArray(dt.primary)) {
            for (const p of dt.primary) {
              const m = p.match(/Mean:\s*([\d.]+)/i);
              if (m) dtMean = parseFloat(m[1]);
              const mx = p.match(/Max:\s*([\d.]+)/i);
              if (mx) dtMax = parseFloat(mx[1]);
            }
          }
        } catch (e) {
          // displayText nicht JSON-parsbar - ignoriern
        }
      }
      const meanVal = (s.mean != null && !isNaN(s.mean)) ? s.mean : (dtMean != null ? dtMean : null);
      const maxVal = (s.max != null && !isNaN(s.max)) ? (typeof s.max === 'object' ? s.max.max : s.max) : (dtMax != null ? dtMax : null);
      return {
        id: roi.uid || ('roi-' + i),
        uid: roi.uid,
        toolName: roi.toolName,
        mean: meanVal != null ? meanVal.toFixed(1) + unit : '-',
        min: (s.min != null && !isNaN(s.min)) ? s.min.toFixed(1) + unit : '-',
        max: (maxVal != null && !isNaN(maxVal)) ? maxVal.toFixed(1) + unit : '-',
        stdDev: (s.stdDev != null && !isNaN(s.stdDev)) ? s.stdDev.toFixed(2) : '-',
        area: (s.area != null && !isNaN(s.area)) ? s.area.toFixed(1) + ' ' + areaUnit : '-',
        count: s.count || '-',
        isEmpty: s.isEmptyArea || false,
        referencedImageId: roi.referencedImageId || imageIds[0] || null,
        sopInstanceUID: roi.SOPInstanceUID || null,
        frameNumber: roi.frameNumber || null,
      };
    });
    setRoiStats(stats);
  }, [measurementService]);

  // Modality des aktiven DisplaySets ermitteln
  useEffect(() => {
    if (!displaySetService) return;
    const updateModality = () => {
      const displaySets = displaySetService.getActiveDisplaySets();
      for (const ds of displaySets) {
        if (ds.Modality) {
          setActiveModality(ds.Modality);
          activeModalityRef.current = ds.Modality;
          break;
        }
      }
    };
    updateModality();
    const sub = displaySetService.subscribe?.(
      displaySetService.EVENTS?.DISPLAY_SETS_CHANGED,
      updateModality
    );
    return () => sub?.unsubscribe?.();
  }, [displaySetService]);

  // Live-Cursor-Wert ueber Cornerstone3D Event abonnieren
  // TODO: Cornerstone3D Probe-Tool Integration fuer Live-Dichtewerte.
  // Aktuell wird der Cursor-Wert nicht aktualisiert (kein Event-Listener
  // implementiert). Die ROI-Statistiken funktionieren unabhaengig davon.
  useEffect(() => {
    if (!cornerstoneViewportService) return;

    // Initiale Messungen und Subscriptions
    updateMeasurements();

    const sub1 = measurementService?.subscribe?.(
      measurementService.EVENTS?.MEASUREMENT_ADDED,
      updateMeasurements
    );
    const sub2 = measurementService?.subscribe?.(
      measurementService.EVENTS?.MEASUREMENT_UPDATED,
      updateMeasurements
    );
    const sub3 = measurementService?.subscribe?.(
      measurementService.EVENTS?.RAW_MEASUREMENT_ADDED,
      updateMeasurements
    );

    return () => {
      sub1?.unsubscribe?.();
      sub2?.unsubscribe?.();
      sub3?.unsubscribe?.();
    };
  }, [cornerstoneViewportService, measurementService, updateMeasurements]);

  // Klick auf ROI -> zur entsprechenden Instanz springen
  const jumpToROI = useCallback((roi) => {
    if (!commandsManager || !roi?.uid) return;
    try {
      commandsManager.runCommand('jumpToMeasurementViewport', {
        annotationUID: roi.uid,
        measurement: roi,
      });
    } catch (err) {
      console.warn('[ROIStats] jumpToMeasurementViewport fehlgeschlagen:', err.message);
    }
  }, [commandsManager]);

  const unit = activeModality === 'CT' ? ' HU' : '';

  const tableRowStyle = {
    borderBottom: '1px solid #333',
    padding: '4px 6px',
    fontSize: '11px',
  };
  const labelStyle = { color: '#999', fontSize: '11px', marginBottom: '2px', marginTop: '8px' };

  return React.createElement('div', {
    style: { padding: '8px', height: '100%', overflow: 'auto', background: '#0d1117' },
    'data-cy': 'roi-stats-panel',
  },
    // Header
    React.createElement('h3', {
      style: { color: '#e0e0e0', fontSize: '14px', margin: '0 0 8px 0', borderBottom: '1px solid #333', paddingBottom: '4px' },
    }, 'ROI-Statistiken'),

    // Modality-Anzeige + Refresh-Button
    React.createElement('div', {
      style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' },
    },
      React.createElement('div', { style: { fontSize: '11px', color: '#999' } }, 'Aktive Modality: ' + activeModality),
      React.createElement('button', {
        style: { padding: '2px 8px', fontSize: '10px', background: '#333', color: '#ccc', border: '1px solid #444', borderRadius: '3px', cursor: 'pointer' },
        onClick: () => updateMeasurements(),
        'data-cy': 'roi-refresh-btn',
      }, 'Aktualisieren'),
    ),

    // Live-Cursor-Wert
    React.createElement('div', {
      style: { background: '#161b22', padding: '8px', borderRadius: '4px', marginBottom: '8px' },
    },
      React.createElement('div', { style: labelStyle }, 'Dichtewert an Cursor' + (activeModality === 'CT' ? ' (HU)' : ' (Signal)')),
      React.createElement('div', {
        style: { fontSize: '20px', fontWeight: 'bold', color: cursorValue != null ? '#4ec9b0' : '#666' },
      }, cursorValue != null ? cursorValue.toFixed(1) + unit : '(bewegen Sie die Maus ueber das Bild)'),
    ),

    // ROI-Statistiken
    React.createElement('div', { style: labelStyle }, 'ROI-Annotationen (' + roiStats.length + ')'),
    roiStats.length === 0
      ? React.createElement('div', {
          style: { color: '#666', fontSize: '12px', padding: '12px', textAlign: 'center', background: '#161b22', borderRadius: '4px' },
        }, 'Keine ROI-Annotation vorhanden.\nZeichnen Sie eine ROI (Rechteck/Ellipse) im Bild.')
      : React.createElement('div', {
          style: { background: '#161b22', borderRadius: '4px', overflow: 'hidden' },
        },
          // Tabelle
          React.createElement('table', {
            style: { width: '100%', borderCollapse: 'collapse' },
          },
            React.createElement('thead', null,
              React.createElement('tr', { style: { background: '#1a2332' } },
                React.createElement('th', { style: { ...tableRowStyle, textAlign: 'left', color: '#999', fontWeight: 'bold' } }, 'ROI'),
                React.createElement('th', { style: { ...tableRowStyle, textAlign: 'right', color: '#999', fontWeight: 'bold' } }, 'Mean'),
                React.createElement('th', { style: { ...tableRowStyle, textAlign: 'right', color: '#999', fontWeight: 'bold' } }, 'Min'),
                React.createElement('th', { style: { ...tableRowStyle, textAlign: 'right', color: '#999', fontWeight: 'bold' } }, 'Max'),
                React.createElement('th', { style: { ...tableRowStyle, textAlign: 'right', color: '#999', fontWeight: 'bold' } }, 'StdDev'),
                React.createElement('th', { style: { ...tableRowStyle, textAlign: 'right', color: '#999', fontWeight: 'bold' } }, 'Flaeche'),
              )
            ),
            React.createElement('tbody', null,
              roiStats.map((roi, i) =>
                React.createElement('tr', {
                  key: roi.id || i,
                  onClick: () => jumpToROI(roi),
                  style: {
                    borderBottom: '1px solid #2a2a3a',
                    cursor: 'pointer',
                    transition: 'background 0.15s',
                  },
                  onMouseEnter: e => { e.currentTarget.style.background = 'rgba(42, 108, 199, 0.15)'; },
                  onMouseLeave: e => { e.currentTarget.style.background = 'transparent'; },
                  title: 'Klick: Zur Instanz dieser ROI springen',
                },
                  React.createElement('td', { style: { ...tableRowStyle, color: '#e0e0e0' } },
                    roi.toolName.replace('ROI', '').replace('StartEnd', '') || 'ROI',
                    roi.isEmpty && React.createElement('span', { style: { color: '#ff6b6b', fontSize: '9px', marginLeft: '4px' } }, '(leer)'),
                  ),
                  React.createElement('td', { style: { ...tableRowStyle, textAlign: 'right', color: '#4ec9b0', fontWeight: 'bold' } }, roi.mean),
                  React.createElement('td', { style: { ...tableRowStyle, textAlign: 'right', color: '#999' } }, roi.min),
                  React.createElement('td', { style: { ...tableRowStyle, textAlign: 'right', color: '#999' } }, roi.max),
                  React.createElement('td', { style: { ...tableRowStyle, textAlign: 'right', color: '#999' } }, roi.stdDev),
                  React.createElement('td', { style: { ...tableRowStyle, textAlign: 'right', color: '#999' } }, roi.area),
                )
              )
            )
          )
        ),

    // Hinweis
    React.createElement('div', {
      style: { color: '#666', fontSize: '10px', marginTop: '12px', padding: '8px', background: '#161b22', borderRadius: '3px', lineHeight: '1.5' },
    },
      React.createElement('div', { style: { color: '#999', fontWeight: 'bold', marginBottom: '4px' } }, 'Anleitung:'),
      '1. Waehlen Sie ein ROI-Werkzeug in der Toolbar (Rechteck-ROI oder Elliptische ROI).\n',
      '2. Zeichnen Sie eine ROI auf das Bild, indem Sie klicken und ziehen.\n',
      '3. Die Statistiken (Mean/Min/Max/StdDev/Flaeche) erscheinen automatisch in der Tabelle.\n',
      '4. Klicken Sie auf eine ROI-Zeile, um zur entsprechenden Bild-Instanz zu springen.\n',
      '5. Bei CT werden Werte in HU (Hounsfield Units) angezeigt, bei MR als Signal-Intensitaet.\n',
      '6. Die Live-Dichtewert-Anzeige erfordert den Probe-Tool (in der Toolbar unter "Dichte").'
    ),
  );
}

export default ROIStatsPanel;
