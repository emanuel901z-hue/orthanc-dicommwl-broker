// StudyComparePanel - Studien-Vergleich und Viewport-Synchronisation
//
// Ermöglicht synchronisiertes Scrollen, Zoomen, Pan und Window/Level
// zwischen zwei oder mehr Viewports. Typischer Anwendungsfall:
// Vergleich aktueller Befund mit Voruntersuchung (Prior).
//
// Features:
//  - Auflistung aller Viewports mit ihren DisplaySets
//  - Sync-Gruppen erstellen (Scroll, Zoom, Pan, WL)
//  - Synchronisation aktivieren/deaktivieren
//  - Schneller Voruntersuchs-Vergleich (Side-by-Side Layout)
//
// Nutzt den Cornerstone3D syncGroupService und viewportGridService.

import React, { useState, useEffect, useCallback } from 'react';

function StudyComparePanel({ servicesManager, commandsManager }) {
  const { viewportGridService, displaySetService, cornerstoneViewportService } =
    servicesManager?.services || {};

  const [viewports, setViewports] = useState([]);
  const [activeViewportId, setActiveViewportId] = useState(null);
  const [syncScroll, setSyncScroll] = useState(true);
  const [syncZoom, setSyncZoom] = useState(true);
  const [syncPan, setSyncPan] = useState(true);
  const [syncWL, setSyncWL] = useState(false);
  const [statusMsg, setStatusMsg] = useState('');

  // Viewports verfolgen
  useEffect(() => {
    if (!viewportGridService) return;

    const updateViewports = () => {
      const state = viewportGridService.getState();
      const vpList = Array.isArray(state?.viewports)
        ? state.viewports
        : Object.values(state?.viewports || {});
      setActiveViewportId(state?.activeViewportId);
      setViewports(vpList.map(vp => {
        const ds = displaySetService?.getDisplaySetByUID?.(vp.displaySetInstanceUIDs?.[0]);
        return {
          viewportId: vp.viewportId,
          viewportType: vp.viewportType,
          displaySetUID: vp.displaySetInstanceUIDs?.[0] || null,
          seriesDescription: ds?.SeriesDescription || ds?.Modality || '(leer)',
          modality: ds?.Modality || '-',
          studyUID: ds?.StudyInstanceUID || '-',
        };
      }));
    };

    updateViewports();
    const EVENTS = viewportGridService.EVENTS || {};
    const subs = [];
    // Nur Events subscriben die tatsaechlich existieren
    for (const evt of [EVENTS.VIEWPORTS_READY, EVENTS.ACTIVE_VIEWPORT_ID_CHANGED, EVENTS.LAYOUT_UPDATED]) {
      if (evt && viewportGridService.subscribe) {
        subs.push(viewportGridService.subscribe(evt, updateViewports));
      }
    }
    return () => {
      subs.forEach(s => s?.unsubscribe?.());
    };
  }, [viewportGridService, displaySetService]);

  // Synchronisation anwenden
  const applySync = useCallback(() => {
    if (viewports.length < 2) {
      setStatusMsg('Mindestens 2 Viewports erforderlich');
      return;
    }

    const { syncGroupService } = servicesManager?.services || {};
    if (!syncGroupService) {
      setStatusMsg('syncGroupService nicht verfuegbar');
      return;
    }

    try {
      const renderingEngine = cornerstoneViewportService?.getRenderingEngine?.();
      if (!renderingEngine) {
        setStatusMsg('RenderingEngine nicht verfuegbar');
        return;
      }

      const viewportIds = viewports.map(v => v.viewportId);
      const reId = renderingEngine.id;

      // Sync-Typen ueber toggleSynchronizer-Command aktivieren
      // OHIF v3.12.5 kennt: cameraPosition, voi, zoomPan, imageSlice
      const syncConfigs = [
        { enabled: syncScroll, type: 'cameraPosition', syncId: 'studyCompare-camera' },
        { enabled: syncZoom, type: 'zoomPan', syncId: 'studyCompare-zoompan' },
        { enabled: syncPan, type: 'zoomPan', syncId: 'studyCompare-zoompan' }, // Pan ist in zoomPan enthalten
        { enabled: syncWL, type: 'voi', syncId: 'studyCompare-voi' },
      ];

      let activatedCount = 0;
      const activeTypes = [];

      for (const config of syncConfigs) {
        if (!config.enabled) continue;

        // Pruefen ob Sync bereits existiert
        const existingSync = syncGroupService.getSynchronizer?.(config.syncId);
        if (existingSync) {
          // Bereits aktiv - nur sicherstellen dass alle Viewports dabei sind
          continue;
        }

        // ueber toggleSynchronizer-Command erstellen
        if (commandsManager) {
          try {
            commandsManager.runCommand('toggleSynchronizer', {
              type: config.type,
              viewports: viewportIds.map(id => ({ viewportId: id })),
              syncId: config.syncId,
            });
            if (!activeTypes.includes(config.type)) {
              activeTypes.push(config.type);
              activatedCount++;
            }
          } catch (cmdErr) {
            console.warn('[StudyCompare] toggleSynchronizer fehlgeschlagen fuer ' + config.type + ':', cmdErr.message);
          }
        }
      }

      // Dedup: zoomPan wurde evtl. zweimal gezaehlt
      const labels = [
        syncScroll && 'Scroll',
        syncZoom && 'Zoom',
        syncPan && 'Pan',
        syncWL && 'WL',
      ].filter(Boolean);

      setStatusMsg('Synchronisation aktiviert fuer ' + viewportIds.length + ' Viewports: ' + labels.join(', '));
    } catch (err) {
      console.error('[StudyCompare] Sync-Fehler:', err);
      setStatusMsg('Sync-Fehler: ' + err.message);
    }
  }, [servicesManager, cornerstoneViewportService, viewports, syncScroll, syncZoom, syncPan, syncWL, commandsManager]);

  // Synchronisation aufheben
  const removeSync = useCallback(() => {
    const { syncGroupService } = servicesManager?.services || {};
    if (!syncGroupService) {
      setStatusMsg('syncGroupService nicht verfuegbar');
      return;
    }

    // Alle Sync-Gruppen entfernen
    const syncIds = ['studyCompare-camera', 'studyCompare-zoompan', 'studyCompare-voi'];
    for (const syncId of syncIds) {
      const sync = syncGroupService.getSynchronizer?.(syncId);
      if (sync) {
        // ueber toggleSynchronizer deaktivieren (enabled -> disabled)
        if (commandsManager) {
          try {
            commandsManager.runCommand('toggleSynchronizer', {
              type: syncGroupService.getSynchronizerType?.(sync) || 'cameraPosition',
              viewports: viewports.map(v => ({ viewportId: v.viewportId })),
              syncId: syncId,
            });
          } catch (e) {
            // Fallback: direkt deaktivieren
            sync.setEnabled?.(false);
          }
        } else {
          sync.setEnabled?.(false);
        }
      }
    }

    setStatusMsg('Synchronisation aufgehoben');
  }, [servicesManager, commandsManager, viewports]);

  // Side-by-Side Layout fuer Vergleich
  const setCompareLayout = useCallback(() => {
    if (!viewportGridService || !commandsManager) {
      setStatusMsg('Services nicht verfuegbar');
      return;
    }

    try {
      // setViewportGridLayout ist der korrekte OHIF v3.12.5 Command
      commandsManager.runCommand('setViewportGridLayout', {
        numRows: 1,
        numCols: 2,
      });
      setStatusMsg('Side-by-Side Layout aktiviert - ziehen Sie Studien in beide Viewports');
    } catch (err) {
      setStatusMsg('Layout-Fehler: ' + err.message);
    }
  }, [viewportGridService, commandsManager]);

  const toggleStyle = (active) => ({
    padding: '6px 10px', border: '1px solid ' + (active ? '#2a6cc7' : '#444'),
    borderRadius: '4px', background: active ? '#2a6cc7' : '#1a1a2e',
    color: active ? '#fff' : '#999', cursor: 'pointer', fontSize: '12px',
    marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '6px',
  });

  return React.createElement('div', {
    style: { padding: '8px', height: '100%', overflow: 'auto', background: '#0d1117' },
    'data-cy': 'study-compare-panel',
  },
    // Header
    React.createElement('h3', {
      style: { color: '#e0e0e0', fontSize: '14px', margin: '0 0 8px 0', borderBottom: '1px solid #333', paddingBottom: '4px' },
    }, 'Studien-Vergleich / Sync'),

    // Layout-Button
    React.createElement('button', {
      style: {
        padding: '8px 12px', background: '#2a6cc7', color: '#fff',
        border: 'none', borderRadius: '4px', cursor: 'pointer',
        fontSize: '12px', fontWeight: 'bold', width: '100%', marginBottom: '12px',
      },
      onClick: setCompareLayout,
    }, 'Side-by-Side Layout (2x1)'),

    // Viewport-Liste
    React.createElement('div', { style: { fontSize: '11px', color: '#999', marginBottom: '4px' } },
      'Viewports (' + viewports.length + '):'),
    React.createElement('div', {
      style: { background: '#161b22', borderRadius: '4px', padding: '6px', marginBottom: '12px' },
    },
      viewports.length === 0
        ? React.createElement('div', { style: { color: '#666', fontSize: '12px', textAlign: 'center' } }, 'Keine Viewports geladen.')
        : viewports.map((vp, i) =>
            React.createElement('div', {
              key: vp.viewportId,
              style: {
                padding: '4px 6px', marginBottom: '2px', borderRadius: '3px',
                background: vp.viewportId === activeViewportId ? 'rgba(42, 108, 199, 0.2)' : 'transparent',
                fontSize: '11px',
              },
            },
              React.createElement('span', { style: { color: '#4ec9b0', fontWeight: 'bold' } }, 'VP' + (i + 1)),
              React.createElement('span', { style: { color: '#999' } }, ' [' + vp.viewportType + '] '),
              React.createElement('span', { style: { color: '#e0e0e0' } }, vp.seriesDescription),
              React.createElement('span', { style: { color: '#666', fontSize: '10px' } }, ' (' + vp.modality + ')'),
            )
          )
    ),

    // Sync-Optionen
    React.createElement('div', { style: { fontSize: '11px', color: '#999', marginBottom: '4px' } }, 'Synchronisation:'),
    React.createElement('div', null,
      React.createElement('label', {
        style: toggleStyle(syncScroll),
        onClick: () => setSyncScroll(!syncScroll),
      }, (syncScroll ? '\u2611' : '\u2610') + ' Scrollen / Slice-Navigation'),
      React.createElement('label', {
        style: toggleStyle(syncZoom),
        onClick: () => setSyncZoom(!syncZoom),
      }, (syncZoom ? '\u2611' : '\u2610') + ' Zoom'),
      React.createElement('label', {
        style: toggleStyle(syncPan),
        onClick: () => setSyncPan(!syncPan),
      }, (syncPan ? '\u2611' : '\u2610') + ' Pan'),
      React.createElement('label', {
        style: toggleStyle(syncWL),
        onClick: () => setSyncWL(!syncWL),
      }, (syncWL ? '\u2611' : '\u2610') + ' Window/Level'),
    ),

    // Sync-Buttons
    React.createElement('div', { style: { display: 'flex', gap: '4px', marginTop: '12px' } },
      React.createElement('button', {
        style: {
          flex: 1, padding: '8px', background: '#2a6cc7', color: '#fff',
          border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '12px', fontWeight: 'bold',
        },
        onClick: applySync,
        disabled: viewports.length < 2,
      }, 'Sync aktivieren'),
      React.createElement('button', {
        style: {
          flex: 1, padding: '8px', background: '#444', color: '#ccc',
          border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '12px',
        },
        onClick: removeSync,
      }, 'Sync aufheben'),
    ),

    // Status
    statusMsg && React.createElement('div', {
      style: { color: '#4ec9b0', fontSize: '11px', padding: '6px', marginTop: '8px', background: '#0a1a1a', borderRadius: '3px' },
    }, statusMsg),

    // Hinweis
    React.createElement('div', {
      style: { color: '#666', fontSize: '10px', marginTop: '12px', padding: '8px', background: '#161b22', borderRadius: '3px', lineHeight: '1.5' },
    },
      React.createElement('div', { style: { color: '#999', fontWeight: 'bold', marginBottom: '4px' } }, 'Anleitung Studien-Vergleich:'),
      React.createElement('div', null, '1. Klicken Sie "Side-by-Side Layout" fuer 2 Viewports nebeneinander.'),
      React.createElement('div', null, '2. Ziehen Sie per Drag&Drop eine Serie aus dem StudyBrowser (links) in den linken Viewport.'),
      React.createElement('div', null, '3. Ziehen Sie eine andere Serie (z.B. Voruntersuchung) in den rechten Viewport.'),
      React.createElement('div', null, '4. Waehlen Sie die Sync-Optionen: Scroll (Slice-Navigation), Zoom, Pan, Window/Level.'),
      React.createElement('div', null, '5. Klicken Sie "Sync aktivieren" - nun folgen beide Viewports den Aktionen im anderen.'),
      React.createElement('div', null, '6. Scrollen Sie in einem Viewport - der andere springt automatisch zur gleichen Position.'),
      React.createElement('div', null, '7. Mit "Sync aufheben" beenden Sie die Synchronisation.'),
      React.createElement('div', { style: { marginTop: '4px' } },
        React.createElement('span', { style: { color: '#4ec9b0' } }, 'Tipp: '),
        'Oeffnen Sie zusaetzlich das ROI-Panel, um in beiden Viewports gleichzeitig Messungen zu vergleichen.'
      )
    ),
  );
}

export default StudyComparePanel;
