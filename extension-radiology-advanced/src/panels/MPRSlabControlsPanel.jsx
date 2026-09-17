// MPRSlabControlsPanel - MPR / Slab / MIP Quick-Controls
//
// Bietet inline Steuerung fuer:
//  - Multiplanare Reformatierung (Axial / Sagittal / Koronar)
//  - Slab-Dicke (Slab Thickness) fuer MIP/minIP/avg
//  - Blend-Mode: MIP, minIP, Average, Off
//  - Viewport-Type: Stack (2D), Volume (MPR), Volume3D (VR)
//
// Ergaenzt das Vessel-Tracking-Panel um interaktive Steuerung
// ohne Protokollwechsel. Nutzt die Cornerstone3D Volume-Viewport-API.

import React, { useState, useEffect, useCallback } from 'react';

// Cornerstone3D BlendMode enum values (from @cornerstonejs/core)
// COMPOSITE_BLEND = 0, MAXIMUM_INTENSITY_BLEND = 1,
// MINIMUM_INTENSITY_BLEND = 2, AVERAGE_INTENSITY_BLEND = 3
const BLEND_MODE_ENUMS = {
  off: 0,
  mip: 1,
  minip: 2,
  avg: 3,
};

function MPRSlabControlsPanel({ servicesManager, commandsManager }) {
  const { cornerstoneViewportService, viewportGridService } =
    servicesManager?.services || {};

  const [activeViewportId, setActiveViewportId] = useState(null);
  const [viewportType, setViewportType] = useState('stack');
  const [orientation, setOrientation] = useState('axial');
  const [slabThickness, setSlabThickness] = useState(0); // 0 = off
  const [blendMode, setBlendMode] = useState('off'); // 'off' | 'mip' | 'minip' | 'avg'
  const [statusMsg, setStatusMsg] = useState('');

  // Aktiven Viewport verfolgen
  useEffect(() => {
    if (!viewportGridService) return;

    const updateState = () => {
      const state = viewportGridService.getState();
      const vpId = state?.activeViewportId;
      setActiveViewportId(vpId);

      if (vpId && cornerstoneViewportService) {
        const csViewport = cornerstoneViewportService.getCornerstoneViewport(vpId);
        if (csViewport) {
          // Viewport-Type ermitteln
          const type = csViewport.constructor?.name || '';
          const isVolume = type.includes('Volume');
          setViewportType(isVolume ? 'volume' : 'stack');

          // Aktuelle Slab-Dicke und Blend-Mode auslesen (nur VolumeViewport)
          if (isVolume) {
            const properties = csViewport.getProperties?.() || {};
            if (properties.slabThickness) {
              setSlabThickness(properties.slabThickness);
            }
            // Blend-Mode ueber getBlendMode auslesen
            const currentBlend = csViewport.getBlendMode?.();
            // Map enum value back to string
            const blendMap = { 0: 'off', 1: 'mip', 2: 'minip', 3: 'avg' };
            if (blendMap[currentBlend]) {
              setBlendMode(blendMap[currentBlend]);
            }
          }
        }
      }
    };

    updateState();
    const sub = viewportGridService.subscribe?.(
      viewportGridService.EVENTS?.ACTIVE_VIEWPORT_ID_CHANGED,
      updateState
    );
    return () => sub?.unsubscribe?.();
  }, [viewportGridService, cornerstoneViewportService]);

  // Orientierung aendern
  const setViewOrientation = useCallback((orient) => {
    setOrientation(orient);
    if (!cornerstoneViewportService || !activeViewportId) return;

    try {
      const csViewport = cornerstoneViewportService.getCornerstoneViewport(activeViewportId);
      if (csViewport && csViewport.setCamera) {
        // Cornerstone3D Kamera-Orientierung setzen
        const orientations = {
          axial: { viewPlaneNormal: [0, 0, 1], viewUp: [0, -1, 0] },
          sagittal: { viewPlaneNormal: [1, 0, 0], viewUp: [0, 0, 1] },
          coronal: { viewPlaneNormal: [0, 1, 0], viewUp: [0, 0, 1] },
        };
        const cam = orientations[orient];
        if (cam) {
          csViewport.setCamera({
            viewPlaneNormal: cam.viewPlaneNormal,
            viewUp: cam.viewUp,
          });
          csViewport.render();
        }
      }

      if (commandsManager) {
        commandsManager.runCommand('setViewportOrientation', {
          viewportId: activeViewportId,
          orientation: orient,
        });
      }

      setStatusMsg('Orientierung: ' + orient);
    } catch (err) {
      setStatusMsg('Orientierungs-Fehler: ' + err.message);
    }
  }, [cornerstoneViewportService, activeViewportId, commandsManager]);

  // Slab-Dicke aendern (nur VolumeViewport)
  const changeSlabThickness = useCallback((thickness) => {
    setSlabThickness(thickness);
    if (!cornerstoneViewportService || !activeViewportId) return;

    try {
      const csViewport = cornerstoneViewportService.getCornerstoneViewport(activeViewportId);
      if (!csViewport) {
        setStatusMsg('Kein Viewport gefunden');
        return;
      }

      // StackViewport unterstuetzt keine Slab-Rekonstruktion
      const typeName = csViewport.constructor?.name || '';
      if (!typeName.includes('Volume')) {
        setStatusMsg('Slab nur im MPR/Volume-Viewport verfuegbar. Bitte zu MPR wechseln.');
        return;
      }

      if (csViewport.setProperties) {
        csViewport.setProperties({
          slabThickness: thickness > 0 ? thickness : undefined,
        });
        csViewport.render();
      }

      setStatusMsg('Slab-Dicke: ' + (thickness > 0 ? thickness + ' mm' : 'aus'));
    } catch (err) {
      setStatusMsg('Slab-Fehler: ' + err.message);
    }
  }, [cornerstoneViewportService, activeViewportId]);

  // Blend-Mode aendern (MIP/minIP/avg) - nur VolumeViewport
  const changeBlendMode = useCallback((mode) => {
    setBlendMode(mode);
    if (!cornerstoneViewportService || !activeViewportId) return;

    try {
      const csViewport = cornerstoneViewportService.getCornerstoneViewport(activeViewportId);
      if (!csViewport) {
        setStatusMsg('Kein Viewport gefunden');
        return;
      }

      // StackViewport unterstuetzt keinen Blend-Mode
      const typeName = csViewport.constructor?.name || '';
      if (!typeName.includes('Volume')) {
        setStatusMsg('MIP nur im MPR/Volume-Viewport verfuegbar. Bitte zu MPR wechseln.');
        return;
      }

      // Blend-Mode muss ueber setBlendMode() gesetzt werden, NICHT ueber setProperties
      const enumValue = BLEND_MODE_ENUMS[mode];
      if (enumValue !== undefined && csViewport.setBlendMode) {
        csViewport.setBlendMode(enumValue);
        csViewport.render();
      }

      setStatusMsg('Blend-Mode: ' + (mode === 'off' ? 'aus' : mode.toUpperCase()));
    } catch (err) {
      setStatusMsg('Blend-Mode-Fehler: ' + err.message);
    }
  }, [cornerstoneViewportService, activeViewportId]);

  // Viewport-Type aendern (ueber viewportGridService)
  const changeViewportType = useCallback((type) => {
    setViewportType(type);
    if (!viewportGridService || !activeViewportId) return;

    try {
      // Viewport-Type kann nur ueber Protocol-Wechsel oder SetDisplaySets
      // geaendert werden. Hier informieren wir den Benutzer.
      const typeName = type === 'stack' ? '2D Stack' : type === 'volume' ? 'MPR Volume' : '3D VR';
      setStatusMsg('Viewport-Type "' + typeName + '": Bitte ueber Layout-Button / Protokoll wechseln');
    } catch (err) {
      setStatusMsg('Viewport-Type-Fehler: ' + err.message);
    }
  }, [viewportGridService, activeViewportId]);

  const btnStyle = (active) => ({
    flex: 1, padding: '8px', border: '1px solid ' + (active ? '#2a6cc7' : '#444'),
    borderRadius: '4px', background: active ? '#2a6cc7' : '#1a1a2e',
    color: active ? '#fff' : '#999', cursor: 'pointer', fontSize: '12px', fontWeight: 'bold',
  });
  const labelStyle = { display: 'block', fontSize: '11px', color: '#999', marginBottom: '4px', marginTop: '12px' };

  return React.createElement('div', {
    style: { padding: '8px', height: '100%', overflow: 'auto', background: '#0d1117' },
    'data-cy': 'mpr-slab-panel',
  },
    // Header
    React.createElement('h3', {
      style: { color: '#e0e0e0', fontSize: '14px', margin: '0 0 8px 0', borderBottom: '1px solid #333', paddingBottom: '4px' },
    }, 'MPR / Slab / MIP Controls'),

    // Viewport-Info
    React.createElement('div', {
      style: { fontSize: '11px', color: '#999', marginBottom: '8px', padding: '4px', background: '#161b22', borderRadius: '3px' },
    }, 'Viewport: ' + (activeViewportId || '(keiner)') + ' | Type: ' + viewportType),

    // Viewport-Type
    React.createElement('label', { style: labelStyle }, 'Viewport-Type:'),
    React.createElement('div', { style: { display: 'flex', gap: '4px' } },
      React.createElement('button', {
        style: btnStyle(viewportType === 'stack'),
        onClick: () => changeViewportType('stack'),
      }, '2D Stack'),
      React.createElement('button', {
        style: btnStyle(viewportType === 'volume'),
        onClick: () => changeViewportType('volume'),
      }, 'MPR Volume'),
      React.createElement('button', {
        style: btnStyle(viewportType === 'volume3d'),
        onClick: () => changeViewportType('volume3d'),
      }, '3D VR'),
    ),

    // Orientierung
    React.createElement('label', { style: labelStyle }, 'Orientierung:'),
    React.createElement('div', { style: { display: 'flex', gap: '4px' } },
      React.createElement('button', {
        style: btnStyle(orientation === 'axial'),
        onClick: () => setViewOrientation('axial'),
      }, 'Axial'),
      React.createElement('button', {
        style: btnStyle(orientation === 'sagittal'),
        onClick: () => setViewOrientation('sagittal'),
      }, 'Sagittal'),
      React.createElement('button', {
        style: btnStyle(orientation === 'coronal'),
        onClick: () => setViewOrientation('coronal'),
      }, 'Koronar'),
    ),

    // Blend-Mode (MIP/minIP/avg)
    React.createElement('label', { style: labelStyle }, 'Blend-Mode (MIP):'),
    React.createElement('div', { style: { display: 'flex', gap: '4px' } },
      React.createElement('button', {
        style: btnStyle(blendMode === 'off'),
        onClick: () => changeBlendMode('off'),
      }, 'Off'),
      React.createElement('button', {
        style: btnStyle(blendMode === 'mip'),
        onClick: () => changeBlendMode('mip'),
      }, 'MIP'),
      React.createElement('button', {
        style: btnStyle(blendMode === 'minip'),
        onClick: () => changeBlendMode('minip'),
      }, 'minIP'),
      React.createElement('button', {
        style: btnStyle(blendMode === 'avg'),
        onClick: () => changeBlendMode('avg'),
      }, 'Avg'),
    ),

    // Slab-Dicke
    React.createElement('label', { style: labelStyle },
      'Slab-Dicke: ' + (slabThickness > 0 ? slabThickness + ' mm' : 'aus (Single-Slice)')
    ),
    React.createElement('div', { style: { display: 'flex', gap: '4px', alignItems: 'center' } },
      React.createElement('button', {
        style: { ...btnStyle(slabThickness === 0), flex: '0 0 auto', padding: '6px 10px' },
        onClick: () => changeSlabThickness(0),
      }, 'Off'),
      React.createElement('input', {
        type: 'range', min: 0, max: 100, value: slabThickness,
        onChange: e => changeSlabThickness(parseInt(e.target.value)),
        style: { flex: 1, cursor: 'pointer' },
        'data-cy': 'slab-thickness-slider',
      }),
      React.createElement('span', {
        style: { fontSize: '11px', color: '#4ec9b0', minWidth: '40px', textAlign: 'right' },
      }, slabThickness + 'mm'),
    ),

    // Quick-Slab-Presets
    React.createElement('div', { style: { display: 'flex', gap: '4px', marginTop: '4px' } },
      [10, 20, 30, 50, 80].map(t =>
        React.createElement('button', {
          key: t,
          style: {
            flex: 1, padding: '4px', border: '1px solid #444', borderRadius: '3px',
            background: slabThickness === t ? '#2a6cc7' : '#333',
            color: slabThickness === t ? '#fff' : '#999',
            cursor: 'pointer', fontSize: '10px',
          },
          onClick: () => changeSlabThickness(t),
        }, t + 'mm')
      )
    ),

    // Status
    statusMsg && React.createElement('div', {
      style: { color: '#4ec9b0', fontSize: '11px', padding: '6px', marginTop: '12px', background: '#0a1a1a', borderRadius: '3px' },
    }, statusMsg),

    // Hinweis
    React.createElement('div', {
      style: { color: '#666', fontSize: '10px', marginTop: '12px', padding: '8px', background: '#161b22', borderRadius: '3px', lineHeight: '1.5' },
    },
      React.createElement('div', { style: { color: '#999', fontWeight: 'bold', marginBottom: '4px' } }, 'Anleitung MPR/MIP:'),
      React.createElement('div', null, '1. Wechseln Sie zunaechst auf "Volume" als Viewport-Type (oben).'),
      React.createElement('div', null, '2. Waehlen Sie die gewuenschte Orientierung (Axial/Sagittal/Koronar).'),
      React.createElement('div', null, '3. Fuer MIP: Klicken Sie "MIP" als Blend-Mode. Es erscheint eine Maximum-Intensitaets-Projektion.'),
      React.createElement('div', null, '4. Stellen Sie die Slab-Dicke ein (Slider oder Presets: 10-80mm). Hoeher = mehr Schichten werden projiziert.'),
      React.createElement('div', null, '5. MIP ist ideal fuer Gefaessdarstellung (CT-Angio, MR-Angio).'),
      React.createElement('div', null, '6. minIP fuer Luft/Fluessigkeit (z.B. Lunge), Avg fuer weichgewebe-Reduced-Darstellung.'),
      React.createElement('div', null, '7. "Off" schaltet die Projektion aus (normale Schicht-Ansicht).'),
      React.createElement('div', { style: { marginTop: '4px' } },
        React.createElement('span', { style: { color: '#ff6b6b' } }, 'Wichtig: '),
        'MIP/Slab funktioniert nur in Volume-Viewports (MPR). Im 2D-Stack-Modus ist es nicht verfuegbar.'),
      React.createElement('div', null, 'Bei MR-Studien: Nutzen Sie das Vessel-Tracking-Panel fuer den MPR-Wechsel, dann hier MIP aktivieren.')
    ),
  );
}

export default MPRSlabControlsPanel;
