// WindowLevelPresetsPanel - Schnellzugriff auf Fensterungs-Presets
//
// Bietet modalitaetsspezifische Window/Level-Presets:
//  CT: Knochen, Lunge, Hirn, Abdomen, Mediastinum, Weichteil
//  MR: T1, T2, FLAIR, PD
//  DX: Thorax, Knochen, Mamma
//
// Die Presets werden ueber den Cornerstone3D-Viewport angewendet
// (setVOI / windowLevel Command). Erkennt automatisch die Modality
// des aktiven Viewports und schlaegt die passenden Presets vor.

import React, { useState, useEffect, useCallback, useMemo } from 'react';

const PRESETS = {
  CT: [
    { name: 'Hirn', windowWidth: 80, windowCenter: 40 },
    { name: 'Knochen', windowWidth: 2000, windowCenter: 400 },
    { name: 'Lunge', windowWidth: 1500, windowCenter: -600 },
    { name: 'Abdomen', windowWidth: 400, windowCenter: 40 },
    { name: 'Mediastinum', windowWidth: 350, windowCenter: 40 },
    { name: 'Weichteil', windowWidth: 400, windowCenter: 50 },
    { name: 'Hirn-Fein', windowWidth: 40, windowCenter: 40 },
    { name: 'Schlaganfall', windowWidth: 35, windowCenter: 35 },
    { name: 'CTA-Kopf', windowWidth: 700, windowCenter: 150 },
    { name: 'CTA-Korpus', windowWidth: 600, windowCenter: 120 },
  ],
  MR: [
    { name: 'T1', windowWidth: 500, windowCenter: 250 },
    { name: 'T2', windowWidth: 800, windowCenter: 400 },
    { name: 'FLAIR', windowWidth: 600, windowCenter: 300 },
    { name: 'PD', windowWidth: 500, windowCenter: 250 },
    { name: 'DWI', windowWidth: 300, windowCenter: 150 },
    { name: 'SWI', windowWidth: 200, windowCenter: 100 },
  ],
  DX: [
    { name: 'Thorax', windowWidth: 4096, windowCenter: 2048 },
    { name: 'Knochen', windowWidth: 2048, windowCenter: 1024 },
    { name: 'Mamma', windowWidth: 4096, windowCenter: 2048 },
  ],
  PT: [
    { name: 'PET-Standard', windowWidth: 5, windowCenter: 2.5 },
    { name: 'PET-Hot', windowWidth: 10, windowCenter: 5 },
    { name: 'PET-SUV', windowWidth: 8, windowCenter: 4 },
  ],
  XA: [
    { name: 'DSA-Standard', windowWidth: 1024, windowCenter: 512 },
    { name: 'DSA-Hell', windowWidth: 2048, windowCenter: 1024 },
  ],
};

function WindowLevelPresetsPanel({ servicesManager, commandsManager }) {
  const { cornerstoneViewportService, displaySetService, viewportGridService } =
    servicesManager?.services || {};

  const [activeModality, setActiveModality] = useState('CT');
  const [activeViewportId, setActiveViewportId] = useState(null);
  const [statusMsg, setStatusMsg] = useState('');

  // Aktive Modality und Viewport verfolgen
  useEffect(() => {
    if (!viewportGridService || !displaySetService) return;

    const updateState = () => {
      const state = viewportGridService.getState();
      const vpId = state?.activeViewportId;
      setActiveViewportId(vpId);

      if (vpId && cornerstoneViewportService) {
        const csViewport = cornerstoneViewportService.getCornerstoneViewport(vpId);
        if (csViewport) {
          const imageData = csViewport.getImageData?.();
          if (imageData) {
            // Modality aus dem aktiven Viewport's DisplaySet ermitteln
            const displaySets = displaySetService.getActiveDisplaySets();
            // Finde das DisplaySet das zum aktiven Viewport gehoert
            const activeVP = state?.viewports?.find?.(v => v.viewportId === vpId) ||
                              Object.values(state?.viewports || {}).find(v => v.viewportId === vpId);
            const activeDSUID = activeVP?.displaySetInstanceUIDs?.[0];
            const activeDS = activeDSUID
              ? displaySets.find(ds => ds.displaySetInstanceUID === activeDSUID)
              : null;
            if (activeDS?.Modality) {
              setActiveModality(activeDS.Modality);
            } else if (displaySets.length > 0 && displaySets[0].Modality) {
              // Fallback: erstes DisplaySet
              setActiveModality(displaySets[0].Modality);
            }
          }
        }
      }
    };

    updateState();
    const sub1 = viewportGridService.subscribe?.(
      viewportGridService.EVENTS?.ACTIVE_VIEWPORT_ID_CHANGED,
      updateState
    );
    const sub2 = viewportGridService.subscribe?.(
      viewportGridService.EVENTS?.VIEWPORTS_READY,
      updateState
    );
    return () => {
      sub1?.unsubscribe?.();
      sub2?.unsubscribe?.();
    };
  }, [viewportGridService, displaySetService, cornerstoneViewportService]);

  // Preset anwenden
  const applyPreset = useCallback((preset) => {
    if (!cornerstoneViewportService || !activeViewportId) {
      setStatusMsg('Kein aktiver Viewport');
      return;
    }

    let applied = false;

    // Primärer Weg: OHIF Command mit korrekten Parametern
    if (commandsManager) {
      try {
        commandsManager.runCommand('setViewportWindowLevel', {
          viewportId: activeViewportId,
          windowWidth: preset.windowWidth,
          windowCenter: preset.windowCenter,
        });
        applied = true;
      } catch (cmdErr) {
        console.warn('[WLPresets] Command fehlgeschlagen, nutze setProperties:', cmdErr.message);
      }
    }

    // Fallback: Direkt ueber Cornerstone3D setProperties mit voiRange
    if (!applied) {
      const csViewport = cornerstoneViewportService.getCornerstoneViewport(activeViewportId);
      if (csViewport && csViewport.setProperties) {
        csViewport.setProperties({
          voiRange: {
            lower: preset.windowCenter - preset.windowWidth / 2,
            upper: preset.windowCenter + preset.windowWidth / 2,
          },
        });
        csViewport.render();
        applied = true;
      }
    }

    if (applied) {
      setStatusMsg(preset.name + ': W=' + preset.windowWidth + ' L=' + preset.windowCenter);
    } else {
      setStatusMsg('Fehler: Keine Methode anwendbar');
    }
  }, [cornerstoneViewportService, activeViewportId, commandsManager]);

  const presets = useMemo(() => PRESETS[activeModality] || PRESETS.CT, [activeModality]);
  const availableModalities = Object.keys(PRESETS);

  const btnStyle = {
    padding: '8px 10px', border: '1px solid #444', borderRadius: '4px',
    background: '#1a2a4a', color: '#e0e0e0', cursor: 'pointer',
    fontSize: '12px', textAlign: 'left', marginBottom: '4px',
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  };
  const modalityBtnStyle = (active) => ({
    padding: '4px 8px', border: 'none', borderRadius: '3px',
    background: active ? '#2a6cc7' : '#333', color: active ? '#fff' : '#999',
    cursor: 'pointer', fontSize: '11px', fontWeight: 'bold',
  });

  return React.createElement('div', {
    style: { padding: '8px', height: '100%', overflow: 'auto', background: '#0d1117' },
    'data-cy': 'wl-presets-panel',
  },
    // Header
    React.createElement('h3', {
      style: { color: '#e0e0e0', fontSize: '14px', margin: '0 0 8px 0', borderBottom: '1px solid #333', paddingBottom: '4px' },
    }, 'Fensterungs-Presets'),

    // Aktiver Viewport
    React.createElement('div', {
      style: { fontSize: '11px', color: '#999', marginBottom: '8px' },
    }, 'Viewport: ' + (activeViewportId || '(keiner)')),

    // Modality-Auswahl
    React.createElement('div', {
      style: { display: 'flex', gap: '2px', marginBottom: '8px', flexWrap: 'wrap' },
    },
      availableModalities.map(mod =>
        React.createElement('button', {
          key: mod,
          style: modalityBtnStyle(activeModality === mod),
          onClick: () => setActiveModality(mod),
        }, mod)
      )
    ),

    // Preset-Liste
    React.createElement('div', null,
      presets.map((preset, i) =>
        React.createElement('button', {
          key: preset.name || preset.description || i,
          style: btnStyle,
          onClick: () => applyPreset(preset),
          'data-cy': 'wl-preset-' + i,
        },
          React.createElement('span', null, preset.name),
          React.createElement('span', {
            style: { color: '#666', fontSize: '10px' },
          }, 'W:' + preset.windowWidth + ' L:' + preset.windowCenter),
        )
      )
    ),

    // Status
    statusMsg && React.createElement('div', {
      style: { color: '#4ec9b0', fontSize: '11px', padding: '4px', marginTop: '8px', background: '#0a1a1a', borderRadius: '3px' },
    }, statusMsg),

    // Hinweis
    React.createElement('div', {
      style: { color: '#666', fontSize: '10px', marginTop: '12px', padding: '6px', background: '#161b22', borderRadius: '3px' },
    }, 'Tipp: Die Modality wird automatisch aus dem aktiven Viewport erkannt. Klicken Sie ein Preset an, um es anzuwenden.'),
  );
}

export default WindowLevelPresetsPanel;
