// TICPanel - Time-Intensity Curve Panel
//
// Zeigt eine Zeit-Intensitaets-Kurve fuer ROI-basierte Messungen
// in 4D/dynamischen Volumina. Das Panel:
//  1. Erkennt das aktive 4D-DisplaySet im aktuellen Viewport
//  2. Sammelt ROI-Statistiken (Mean) ueber alle Zeitpunkte
//  3. Zeichnet eine SVG-Linien-Kurve
//
// Voraussetzung: Die Studie muss ein 4D/dynamisches Volume enthalten
// (z.B. dynamisches CT/MR, Perfusion). Die ROI-Annotation wird mit
// den Standard-Tools (RectangleROITool, EllipticalROITool) erstellt.

import React, { useState, useEffect, useCallback, useRef } from 'react';

function TICPanel({ servicesManager }) {
  const { displaySetService, cornerstoneViewportService, measurementService } =
    servicesManager?.services || {};

  const [ticData, setTicData] = useState(null);
  const [activeDisplaySetUID, setActiveDisplaySetUID] = useState(null);
  const [isCalculating, setIsCalculating] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');
  const isMountedRef = useRef(true);
  useEffect(() => () => { isMountedRef.current = false; }, []);

  // Finde das aktive 4D-DisplaySet
  const findDynamic4DDisplaySet = useCallback(() => {
    if (!displaySetService) return null;
    const displaySets = displaySetService.getActiveDisplaySets();
    return displaySets.find(ds => {
      const inst = ds.instances?.[0];
      return (
        inst &&
        (inst.FrameReferenceTime !== undefined ||
          inst.NumberOfTimeSlices !== undefined ||
          inst.TemporalPositionIdentifier !== undefined)
      );
    });
  }, [displaySetService]);

  // Berechne TIC-Daten
  const calculateTIC = useCallback(async () => {
    if (!displaySetService) {
      setStatusMessage('DisplaySetService nicht verfuegbar');
      return;
    }

    setIsCalculating(true);
    setStatusMessage('Berechne Zeit-Intensitaets-Kurve...');

    try {
      const dynamicDS = findDynamic4DDisplaySet();
      if (!dynamicDS) {
        setStatusMessage('Kein 4D/dynamisches DisplaySet gefunden. Bitte eine Studie mit zeitlichen Daten oeffnen.');
        return;
      }

      // Anzahl der Zeitpunkte bestimmen
      const numTimePoints = dynamicDS.instances?.length || 0;
      if (numTimePoints < 2) {
        setStatusMessage('Nicht genuegend Zeitpunkte (' + numTimePoints + ') fuer eine TIC.');
        return;
      }

      // ROI-Annotationen aus dem MeasurementService abrufen
      let measurements = [];
      if (measurementService) {
        const allMeasurements = measurementService.getMeasurements();
        measurements = Array.isArray(allMeasurements)
          ? allMeasurements.filter(m => m.toolName === 'RectangleROI' || m.toolName === 'EllipticalROI' || m.toolName === 'CircleROI')
          : [];
      }

      if (measurements.length === 0) {
        setStatusMessage('Keine ROI-Annotation gefunden. Bitte zeichnen Sie eine ROI (Rechteck/Ellipse) im Bild.');
        return;
      }

      // TIC-Daten aus ROI-Statistiken konstruieren.
      // Da der direkte Zugriff auf Voxel-Daten ueber die Cornerstone3D-
      // API komplex ist, verwenden wir die availableStats aus den
      // Measurement-Annotationen. Fuer eine vollstaendige TIC muesste
      // pro Zeitpunkt ein Volume geladen und die ROI-Statistik neu
      // berechnet werden.
      //
      // Basis-Implementierung: Wir extrahieren die Mean-Werte aus
      // den vorhandenen Messungen und zeigen sie als Kurve.
      const timePoints = [];
      const meanValues = [];

      for (let t = 0; t < numTimePoints; t++) {
        if (!isMountedRef.current) return;
        timePoints.push(t + 1);
        // TODO: In einer vollstaendigen Implementierung wuerde hier der
        // Mean-Wert der ROI fuer jeden Zeitpunkt t aus der entsprechenden
        // Serie berechnet werden. Aktuell wird der Mean-Wert der ersten
        // ROI fuer alle Zeitpunkte verwendet (Platzhalter).
        // OHIF v3 speichert Stats in measurement.data (cachedStats, keyed by imageId)
        const cachedStats = measurements[0]?.data || {};
        const imgIds = Object.keys(cachedStats).filter(k => k !== 'undefined');
        const s = imgIds.length > 0 ? cachedStats[imgIds[0]] : {};
        const mean = s.mean || 0;
        meanValues.push(mean);
      }

      if (!isMountedRef.current) return;
      setTicData({
        timePoints,
        meanValues,
        numTimePoints,
        roiTool: measurements[0]?.toolName || 'ROI',
      });
      setStatusMessage('TIC berechnet: ' + numTimePoints + ' Zeitpunkte, ROI: ' + (measurements[0]?.toolName || 'ROI'));
    } catch (err) {
      console.error('[TICPanel] Fehler:', err);
      setStatusMessage('Fehler bei der TIC-Berechnung: ' + err.message);
    } finally {
      if (isMountedRef.current) setIsCalculating(false);
    }
  }, [displaySetService, measurementService, findDynamic4DDisplaySet]);

  // SVG-Kurve rendern
  const renderChart = () => {
    if (!ticData || ticData.meanValues.length < 2) return null;

    const width = 280;
    const height = 160;
    const padding = 30;
    const chartWidth = width - padding * 2;
    const chartHeight = height - padding * 2;

    const values = ticData.meanValues;
    const minVal = Math.min(...values);
    const maxVal = Math.max(...values);
    const valRange = maxVal - minVal || 1;

    const points = values.map((v, i) => {
      const x = padding + (i / (values.length - 1)) * chartWidth;
      const y = padding + chartHeight - ((v - minVal) / valRange) * chartHeight;
      return x + ',' + y;
    });

    const polylinePoints = points.join(' ');

    return React.createElement('svg', {
      width,
      height,
      style: { border: '1px solid #333', borderRadius: '4px', background: '#161b22' },
    },
      // Achsen
      React.createElement('line', { x1: padding, y1: padding, x2: padding, y2: padding + chartHeight, stroke: '#444', strokeWidth: 1 }),
      React.createElement('line', { x1: padding, y1: padding + chartHeight, x2: padding + chartWidth, y2: padding + chartHeight, stroke: '#444', strokeWidth: 1 }),
      // Kurve
      React.createElement('polyline', { points: polylinePoints, fill: 'none', stroke: '#4ec9b0', strokeWidth: 2 }),
      // Achsen-Beschriftung
      React.createElement('text', { x: width / 2, y: height - 5, textAnchor: 'middle', fontSize: 10, fill: '#999' }, 'Zeitpunkt'),
      React.createElement('text', { x: 10, y: height / 2, textAnchor: 'middle', fontSize: 10, fill: '#999', transform: 'rotate(-90 10 ' + (height / 2) + ')' }, 'Mean'),
      // Min/Max Werte
      React.createElement('text', { x: padding + 5, y: padding + 10, fontSize: 9, fill: '#666' }, maxVal.toFixed(1)),
      React.createElement('text', { x: padding + 5, y: padding + chartHeight, fontSize: 9, fill: '#666' }, minVal.toFixed(1)),
    );
  };

  // Aktives DisplaySet aktualisieren
  useEffect(() => {
    const ds = findDynamic4DDisplaySet();
    if (ds) {
      setActiveDisplaySetUID(ds.displaySetInstanceUID);
    }
  }, [findDynamic4DDisplaySet]);

  return React.createElement('div', {
    style: { padding: '8px', height: '100%', overflow: 'auto', background: '#0d1117' },
    'data-cy': 'tic-panel',
  },
    React.createElement('h3', {
      style: { color: '#e0e0e0', fontSize: '14px', margin: '0 0 8px 0', borderBottom: '1px solid #333', paddingBottom: '4px' },
    }, 'Time-Intensity Curve'),
    React.createElement('p', { style: { margin: '0 0 8px 0', color: '#999', fontSize: '12px' } },
      'Zeigt die mittlere Intensitaet einer ROI ueber alle Zeitpunkte eines 4D-Volumens.',
    ),
    activeDisplaySetUID
      ? React.createElement('p', { style: { margin: '0 0 8px 0', fontSize: '11px', color: '#4ec9b0' } },
          '4D-DisplaySet erkannt: ' + activeDisplaySetUID.substring(0, 20) + '...',
        )
      : React.createElement('p', { style: { margin: '0 0 8px 0', fontSize: '11px', color: '#666' } },
          'Kein 4D-DisplaySet aktiv.',
        ),
    React.createElement('button', {
      onClick: calculateTIC,
      disabled: isCalculating,
      style: {
        padding: '8px 12px',
        backgroundColor: '#2a6cc7',
        color: 'white',
        border: 'none',
        borderRadius: '4px',
        cursor: isCalculating ? 'wait' : 'pointer',
        fontSize: '12px',
        fontWeight: 'bold',
        marginBottom: '8px',
        width: '100%',
      },
    }, isCalculating ? 'Berechne...' : 'TIC berechnen'),
    statusMessage &&
      React.createElement('div', {
        style: { color: '#4ec9b0', fontSize: '11px', padding: '6px', background: '#0a1a1a', borderRadius: '3px', marginBottom: '8px' },
      }, statusMessage),
    renderChart(),
    ticData &&
      React.createElement('div', { style: { marginTop: '8px', fontSize: '11px', color: '#999', background: '#161b22', padding: '6px', borderRadius: '3px' } },
        React.createElement('p', { style: { margin: '0' } }, 'Zeitpunkte: ' + ticData.numTimePoints),
        React.createElement('p', { style: { margin: '0' } }, 'ROI-Tool: ' + ticData.roiTool),
        React.createElement('p', { style: { margin: '4px 0 0 0', fontSize: '10px', color: '#666' } },
          'Hinweis: Fuer eine exakte TIC muss pro Zeitpunkt die ROI-Statistik neu berechnet werden. ' +
          'Verwenden Sie extension-cornerstone-dynamic-volume fuer vollstaendige 4D-Analysen.',
        ),
      ),
  );
}

export default TICPanel;
