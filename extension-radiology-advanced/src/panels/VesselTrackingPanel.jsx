// VesselTrackingPanel - Vessel Tracking Info Panel
//
// OHIF v3.12.5 enthlt keine dedizierte Vessel-Tracking-Extension.
// Dieses Panel bietet:
//  - MIP-basierte Gefaedarstellung (Maximum Intensity Projection)
//  - Wechsel zu MIP/MPR+MIP Hanging Protocols
//  - Anleitung zur manuellen Gefaessvermessung
//  - Verfuegbare Mess-Tools fuer gefaessspezifische Analysen
//
// Fuer automatisierte Centerline-Extraktion und Gefaesstracking
// muesste eine eigene Cornerstone3D-Tool-Extension entwickelt
// werden (Vesselness-Filter, Marching Cubes, Centerline-Algorithmus).

import React, { useState, useCallback, useEffect } from 'react';

function VesselTrackingPanel({ servicesManager, commandsManager }) {
  const [activeProtocol, setActiveProtocol] = useState('');
  const [currentModality, setCurrentModality] = useState('');

  // Aktive Modality ermitteln
  useEffect(() => {
    if (!servicesManager) return;
    const { displaySetService, viewportGridService } = servicesManager.services || {};
    if (!displaySetService || !viewportGridService) return;

    const updateModality = () => {
      const displaySets = displaySetService.getActiveDisplaySets();
      if (displaySets.length > 0 && displaySets[0].Modality) {
        setCurrentModality(displaySets[0].Modality);
      }
    };

    updateModality();
    const sub = viewportGridService.subscribe?.(
      viewportGridService.EVENTS?.ACTIVE_VIEWPORT_ID_CHANGED,
      updateModality
    );
    return () => sub?.unsubscribe?.();
  }, [servicesManager]);

  const switchToMIP = useCallback(() => {
    if (!commandsManager) return;
    // Modality-spezifische Protokoll-Auswahl
    if (currentModality === 'MR') {
      // MR hat kein eigenes MIP-Protokoll, verwende mr-mpr
      const { hangingProtocolService } = servicesManager?.services || {};
      if (hangingProtocolService) {
        hangingProtocolService.setProtocol('mr-mpr');
        setActiveProtocol('mr-mpr (MPR, dann MIP im MPR-Panel aktivieren)');
      }
    } else {
      commandsManager.runCommand('switchToMIPProtocol');
      setActiveProtocol('ct-mip');
    }
  }, [commandsManager, currentModality, servicesManager]);

  const switchToMPRmip = useCallback(() => {
    if (!commandsManager) return;
    if (currentModality === 'MR') {
      const { hangingProtocolService } = servicesManager?.services || {};
      if (hangingProtocolService) {
        hangingProtocolService.setProtocol('mr-mpr');
        setActiveProtocol('mr-mpr (MPR, dann MIP im MPR-Panel aktivieren)');
      }
    } else {
      commandsManager.runCommand('switchToMPRmipProtocol');
      setActiveProtocol('ct-mpr-mip');
    }
  }, [commandsManager, currentModality, servicesManager]);

  const containerStyle = {
    padding: '8px',
    fontSize: '13px',
    background: '#0d1117',
    height: '100%',
    overflow: 'auto',
  };

  const sectionStyle = {
    margin: '8px 0',
    padding: '8px',
    backgroundColor: '#161b22',
    borderRadius: '4px',
    border: '1px solid #333',
  };

  const buttonStyle = {
    padding: '8px 12px',
    backgroundColor: '#2a6cc7',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '12px',
    fontWeight: 'bold',
    marginRight: '6px',
    marginBottom: '4px',
  };

  const toolListStyle = {
    margin: '4px 0',
    paddingLeft: '16px',
    fontSize: '11px',
    color: '#999',
  };

  return React.createElement('div', { style: containerStyle, 'data-cy': 'vessel-tracking-panel' },
    React.createElement('h3', {
      style: { color: '#e0e0e0', fontSize: '14px', margin: '0 0 8px 0', borderBottom: '1px solid #333', paddingBottom: '4px' },
    }, 'Vessel Tracking'),

    React.createElement('p', { style: { margin: '0 0 8px 0', color: '#999', fontSize: '12px' } },
      'OHIF v3.12.5 enthaelt keine automatisierte Gefaesstracking-Funktion. ' +
      'MIP-Rendering und manuelle Messwerkzeuge stehen jedoch zur Verfuegung.',
    ),

    // MIP-Protokoll-Wechsel
    React.createElement('div', { style: sectionStyle },
      React.createElement('p', { style: { margin: '0 0 6px 0', fontWeight: 'bold', fontSize: '12px', color: '#e0e0e0' } }, 'MIP-Rendering'),
      React.createElement('p', { style: { margin: '0 0 6px 0', fontSize: '11px', color: '#999' } },
        'Maximum Intensity Projection (MIP) zeigt die hellsten Voxels entlang einer Projektionsachse. ' +
        'Ideal fuer Gefaedarstellung (CT-Angiographie).',
      ),
      React.createElement('button', { style: buttonStyle, onClick: switchToMIP },
        currentModality === 'MR' ? 'MPR aktivieren (fuer MIP)' : 'MIP (1x3: MIP/MinIP/Avg)'),
      React.createElement('button', { style: buttonStyle, onClick: switchToMPRmip },
        currentModality === 'MR' ? 'MPR aktivieren (fuer MIP)' : 'MPR + MIP (2x2)'),
      currentModality === 'MR' &&
        React.createElement('p', { style: { margin: '4px 0 0 0', fontSize: '10px', color: '#ffd700' } },
          'Hinweis: Fuer MR-Studien gibt es kein CT-MIP-Protokoll. Bitte MPR aktivieren und dann im MPR/Slab-Panel MIP einstellen.',
        ),
      activeProtocol &&
        React.createElement('p', { style: { margin: '4px 0 0 0', fontSize: '10px', color: '#4ec9b0' } },
          'Aktiv: ' + activeProtocol,
        ),
    ),

    // Verfuegbare Mess-Tools
    React.createElement('div', { style: sectionStyle },
      React.createElement('p', { style: { margin: '0 0 4px 0', fontWeight: 'bold', fontSize: '12px', color: '#e0e0e0' } }, 'Gefaess-Messwerkzeuge'),
      React.createElement('ul', { style: toolListStyle },
        React.createElement('li', null, 'LengthTool - Gefaessdurchmesser, Laenge'),
        React.createElement('li', null, 'AngleTool - Abgangswinkel, Bifurkationswinkel'),
        React.createElement('li', null, 'CobbAngleTool - Wirbelsaeulenwinkel'),
        React.createElement('li', null, 'RectangleROITool - ROI-Dichte (HU)'),
        React.createElement('li', null, 'EllipticalROITool - Gefaessquerschnitt, Mean/StdDev'),
        React.createElement('li', null, 'ProbeTool - Pixel-Wert (HU) an Punkt'),
        React.createElement('li', null, 'BidirectionalTool - Laenge + Breite (z.B. Aneurysma)'),
      ),
    ),

    // Anleitung
    React.createElement('div', { style: sectionStyle },
      React.createElement('p', { style: { margin: '0 0 4px 0', fontWeight: 'bold', fontSize: '12px', color: '#e0e0e0' } }, 'Vorgehen'),
      React.createElement('ol', { style: { ...toolListStyle, listStyleType: 'decimal' } },
        React.createElement('li', null, 'MIP-Protokoll aktivieren (Button oben)'),
        React.createElement('li', null, 'Slab-Dicke im Viewport einstellen (Viewport-Settings)'),
        React.createElement('li', null, 'ROI-Tool fuer Dichtemessung verwenden'),
        React.createElement('li', null, 'Length-Tool fuer Durchmesser/Laenge verwenden'),
        React.createElement('li', null, 'Angle-Tool fuer Abgangswinkel verwenden'),
      ),
    ),

    // Hinweis
    React.createElement('p', { style: { margin: '8px 0 0 0', fontSize: '10px', color: '#666', background: '#161b22', padding: '6px', borderRadius: '3px' } },
      'Fuer automatisiertes Gefaesstracking (Centerline-Extraktion, ' +
      'Vesselness-Filter) ist eine Custom-Tool-Entwicklung erforderlich. ' +
      'Die Cornerstone3D-Tools-API unterstuetzt die Integration eigener ' +
      'Annotation-Tools.',
    ),
  );
}

export default VesselTrackingPanel;
