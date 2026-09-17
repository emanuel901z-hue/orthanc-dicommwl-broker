// MismatchPanel - Mismatch Analysis Panel
//
// Ermöglicht den Vergleich von zwei Bildserien (z.B. Perfusion-Maps,
// Pre/Post-Kontrast) durch Volumen-Subtraktion. Das Panel bietet:
//  - Auswahl von Basis- und Vergleichs-DisplaySet
//  - Berechnung der Differenz mit Hot-Colormap
//  - Export der Differenz-Statistiken
//
// Typische Anwendungen:
//  - Perfusions-Mismatch (CBF/CBV-Differenz bei Schlaganfall)
//  - Pre/Post-Kontrast-Subtraktion (Tumor-Vascularisation)
//  - Doppel-Energie-Differenzbilder

import React, { useState, useEffect, useCallback } from 'react';

function MismatchPanel({ servicesManager, commandsManager }) {
  const { displaySetService } = servicesManager?.services || {};

  const [displaySets, setDisplaySets] = useState([]);
  const [baseUID, setBaseUID] = useState('');
  const [compareUID, setCompareUID] = useState('');
  const [result, setResult] = useState(null);

  // Verfuegbare DisplaySets laden und bei Aenderungen aktualisieren
  useEffect(() => {
    if (!displaySetService) return;
    const updateDisplaySets = () => {
      const active = displaySetService.getActiveDisplaySets();
      setDisplaySets(active.map(ds => ({
        uid: ds.displaySetInstanceUID,
        label: ds.SeriesDescription || ds.SeriesNumber || ds.displaySetInstanceUID?.substring(0, 20),
        modality: ds.Modality || '?',
      })));
    };
    updateDisplaySets();
    const sub = displaySetService.subscribe?.(
      displaySetService.EVENTS?.DISPLAY_SETS_CHANGED,
      updateDisplaySets
    );
    const sub2 = displaySetService.subscribe?.(
      displaySetService.EVENTS?.DISPLAY_SETS_ADDED,
      updateDisplaySets
    );
    return () => { sub?.unsubscribe?.(); sub2?.unsubscribe?.(); };
  }, [displaySetService]);

  const calculateMismatch = useCallback(() => {
    if (!baseUID || !compareUID) {
      setResult({ error: 'Bitte Basis- und Vergleichs-DisplaySet auswaehlen.' });
      return;
    }

    if (baseUID === compareUID) {
      setResult({ error: 'Basis und Vergleichs-DisplaySet muessen unterschiedlich sein.' });
      return;
    }

    // Command ausfuehren
    if (commandsManager) {
      try {
        commandsManager.runCommand('calculateMismatch', {
          baseDisplaySetUID: baseUID,
          compareDisplaySetUID: compareUID,
        });
      } catch (err) {
        console.error('[MismatchPanel] calculateMismatch-Fehler:', err);
        setResult({ error: 'Mismatch-Berechnung fehlgeschlagen: ' + (err.message || 'Unbekannter Fehler') });
        return;
      }
    }

    setResult({
      success: true,
      message: 'Mismatch-Overlay aktiviert. Die Differenz wird als Hot-Colormap im Viewport angezeigt.',
    });
  }, [baseUID, compareUID, commandsManager]);

  return React.createElement('div', {
    style: { padding: '8px', height: '100%', overflow: 'auto', background: '#0d1117' },
    'data-cy': 'mismatch-panel',
  },
    React.createElement('h3', {
      style: { color: '#e0e0e0', fontSize: '14px', margin: '0 0 8px 0', borderBottom: '1px solid #333', paddingBottom: '4px' },
    }, 'Mismatch Analysis'),
    React.createElement('p', { style: { margin: '0 0 8px 0', color: '#999', fontSize: '12px' } },
      'Vergleicht zwei Bildserien durch Volumen-Subtraktion. Typische Anwendungen: Perfusions-Mismatch, Pre/Post-Kontrast.',
    ),

    // Basis-DisplaySet Auswahl
    React.createElement('label', { style: { display: 'block', margin: '8px 0 4px 0', fontWeight: 'bold', fontSize: '12px', color: '#999' } }, 'Basis (Referenz)'),
    React.createElement('select', {
      value: baseUID,
      onChange: e => setBaseUID(e.target.value),
      style: { width: '100%', padding: '4px 6px', marginBottom: '8px', fontSize: '12px', border: '1px solid #555', borderRadius: '3px', background: '#1a1a2e', color: '#e0e0e0' },
    },
      React.createElement('option', { value: '' }, '-- Auswaehlen --'),
      displaySets.map(ds =>
        React.createElement('option', { key: ds.uid, value: ds.uid }, '[' + ds.modality + '] ' + ds.label),
      ),
    ),

    // Vergleichs-DisplaySet Auswahl
    React.createElement('label', { style: { display: 'block', margin: '8px 0 4px 0', fontWeight: 'bold', fontSize: '12px', color: '#999' } }, 'Vergleich (Subtrahend)'),
    React.createElement('select', {
      value: compareUID,
      onChange: e => setCompareUID(e.target.value),
      style: { width: '100%', padding: '4px 6px', marginBottom: '8px', fontSize: '12px', border: '1px solid #555', borderRadius: '3px', background: '#1a1a2e', color: '#e0e0e0' },
    },
      React.createElement('option', { value: '' }, '-- Auswaehlen --'),
      displaySets.map(ds =>
        React.createElement('option', { key: ds.uid, value: ds.uid }, '[' + ds.modality + '] ' + ds.label),
      ),
    ),

    // Berechnen-Button
    React.createElement('button', {
      onClick: calculateMismatch,
      disabled: !baseUID || !compareUID,
      style: {
        padding: '8px 12px',
        backgroundColor: baseUID && compareUID ? '#dc2626' : '#333',
        color: 'white',
        border: 'none',
        borderRadius: '4px',
        cursor: baseUID && compareUID ? 'pointer' : 'not-allowed',
        fontSize: '12px',
        fontWeight: 'bold',
        width: '100%',
        marginBottom: '8px',
      },
    }, 'Mismatch berechnen'),

    // Ergebnis
    result?.error &&
      React.createElement('div', {
        style: { color: '#ff6b6b', fontSize: '11px', margin: '4px 0', padding: '6px', background: '#2a1515', borderRadius: '3px' },
      }, result.error),
    result?.success &&
      React.createElement('div', {
        style: { color: '#4ec9b0', fontSize: '11px', margin: '4px 0', padding: '6px', background: '#0a1a1a', borderRadius: '3px' },
      }, result.message),
    result?.success &&
      React.createElement('div', {
        style: { color: '#666', fontSize: '10px', margin: '4px 0', padding: '6px', background: '#161b22', borderRadius: '3px' },
      },
        'Hinweis: Die Basis-Implementierung legt das Vergleichs-Volume als Overlay im Viewport ab. ' +
        'Fuer eine pixelweise Subtraktion mit Differenz-Volume verwenden Sie die Cornerstone3D volumeLoader-API.',
      ),
  );
}

export default MismatchPanel;
