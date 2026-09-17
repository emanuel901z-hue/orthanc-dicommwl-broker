// HotkeyHelpPanel - Tastenkuerzel-Uebersicht mit Suchfunktion
//
// Zeigt alle verfuegbaren Tastenkuerzel (Hotkeys) mit Beschreibung.
// Features:
//  - Suche nach Command-Name oder Tastenkombination
//  - Gruppierung nach Kategorien
//  - Anzeige der zugewiesenen Tasten
//  - Hinweis auf Anpassbarkeit ueber die OHIF-Einstellungen
//
// Nutzt den hotkeysManager von OHIF.

import React, { useState, useEffect, useMemo } from 'react';

function HotkeyHelpPanel({ servicesManager, commandsManager, extensionManager }) {
  // hotkeysManager ist in OHIF v3 ueber den AppContext verfuegbar,
  // nicht direkt ueber servicesManager. Wir versuchen mehrere Pfade.
  const hotkeysManager = servicesManager?.hotkeysManager ||
                         servicesManager?.services?.hotkeysManager ||
                         extensionManager?.hotkeysManager ||
                         null;

  const [hotkeys, setHotkeys] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeCategory, setActiveCategory] = useState('all');

  // Hotkeys laden
  useEffect(() => {
    if (!hotkeysManager) {
      // Fallback 1: Hotkeys aus window.config lesen
      const configHotkeys = (typeof window !== 'undefined' && window && window.config) ? window.config.hotkeys : undefined;
      if (configHotkeys && typeof configHotkeys === 'object') {
        const list = Object.entries(configHotkeys).map(([key, def]) => {
          // OHIF v3 hotkeys config: Werte sind Objekte mit {command, label, keys}
          // oder direkte key-Strings
          if (typeof def === 'object' && def !== null) {
            return {
              command: def.command || key,
              label: def.label || key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
              keys: Array.isArray(def.keys) ? def.keys.join(' + ') : (def.keys || ''),
              category: categorizeCommand(def.command || key),
            };
          }
          // Fallback: def ist ein String oder Array von keys
          return {
            command: key,
            label: key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
            keys: Array.isArray(def) ? def.join(' + ') : (def || ''),
            category: categorizeCommand(key),
          };
        });
        setHotkeys(list.length > 0 ? list : getDefaultHotkeys());
      } else {
        // Fallback 2: Standard-Hotkeys
        setHotkeys(getDefaultHotkeys());
      }
      return;
    }

    try {
      // Hotkeys aus dem Manager auslesen
      const defs = hotkeysManager.getHotkeyDefinitions?.() ||
                   hotkeysManager.hotkeyDefinitions ||
                   [];
      const list = Array.isArray(defs)
        ? defs.map(d => ({
            command: d.command || d.commandName || '',
            label: d.label || d.description || d.command || '',
            keys: Array.isArray(d.keys) ? d.keys.join(' + ') : (d.keys || ''),
            category: categorizeCommand(d.command || d.commandName || ''),
          }))
        : Object.entries(defs).map(([command, def]) => ({
            command,
            label: def.label || def.description || command,
            keys: Array.isArray(def.keys) ? def.keys.join(' + ') : (def.keys || ''),
            category: categorizeCommand(command),
          }));
      setHotkeys(list.length > 0 ? list : getDefaultHotkeys());
    } catch (e) {
      console.warn('[HotkeyHelp] Hotkeys konnten nicht geladen werden:', e);
      setHotkeys(getDefaultHotkeys());
    }
  }, [hotkeysManager]);

  // Gefilterte Hotkeys
  const filteredHotkeys = useMemo(() => {
    let result = hotkeys;
    if (activeCategory !== 'all') {
      result = result.filter(h => h.category === activeCategory);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      result = result.filter(h =>
        h.command.toLowerCase().includes(q) ||
        h.label.toLowerCase().includes(q) ||
        h.keys.toLowerCase().includes(q)
      );
    }
    return result;
  }, [hotkeys, activeCategory, searchQuery]);

  // Kategorien mit Zaehler
  const categories = useMemo(() => {
    const cats = {};
    hotkeys.forEach(h => {
      cats[h.category] = (cats[h.category] || 0) + 1;
    });
    return cats;
  }, [hotkeys]);

  const inputStyle = {
    width: '100%', padding: '4px 6px', marginBottom: '8px',
    border: '1px solid #555', borderRadius: '3px', background: '#1a1a2e',
    color: '#e0e0e0', fontSize: '12px',
  };
  const catBtnStyle = (active) => ({
    padding: '3px 6px', border: 'none', borderRadius: '3px',
    background: active ? '#2a6cc7' : '#333', color: active ? '#fff' : '#999',
    cursor: 'pointer', fontSize: '10px', fontWeight: 'bold',
  });
  const keyBadgeStyle = {
    display: 'inline-block', padding: '2px 6px', background: '#2a2a4a',
    border: '1px solid #4a4a6a', borderRadius: '3px', color: '#4ec9b0',
    fontFamily: 'monospace', fontSize: '11px', fontWeight: 'bold',
  };

  return React.createElement('div', {
    style: { padding: '8px', height: '100%', overflow: 'auto', background: '#0d1117' },
    'data-cy': 'hotkey-help-panel',
  },
    // Header
    React.createElement('h3', {
      style: { color: '#e0e0e0', fontSize: '14px', margin: '0 0 8px 0', borderBottom: '1px solid #333', paddingBottom: '4px' },
    }, 'Tastenkuerzel'),

    // Suche
    React.createElement('input', {
      type: 'text', style: inputStyle, placeholder: 'Suche nach Command oder Taste...',
      value: searchQuery,
      onChange: e => setSearchQuery(e.target.value),
      'data-cy': 'hotkey-search',
    }),

    // Kategorien-Filter
    React.createElement('div', {
      style: { display: 'flex', gap: '2px', marginBottom: '8px', flexWrap: 'wrap' },
    },
      React.createElement('button', {
        style: catBtnStyle(activeCategory === 'all'),
        onClick: () => setActiveCategory('all'),
      }, 'Alle (' + hotkeys.length + ')'),
      Object.entries(categories).map(([cat, count]) =>
        React.createElement('button', {
          key: cat,
          style: catBtnStyle(activeCategory === cat),
          onClick: () => setActiveCategory(cat),
        }, cat + ' (' + count + ')')
      )
    ),

    // Hotkey-Liste
    filteredHotkeys.length === 0
      ? React.createElement('div', {
          style: { color: '#666', fontSize: '12px', padding: '12px', textAlign: 'center' },
        }, hotkeys.length === 0 ? 'Keine Hotkeys verfuegbar.' : 'Keine Treffer fuer Suche.')
      : React.createElement('div', {
          style: { background: '#161b22', borderRadius: '4px', maxHeight: '500px', overflow: 'auto' },
        },
          filteredHotkeys.map((h, i) =>
            React.createElement('div', {
              key: h.command || h.label || i,
              style: {
                padding: '6px 8px', borderBottom: '1px solid #2a2a3a',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                fontSize: '11px',
              },
              'data-cy': 'hotkey-row',
            },
              React.createElement('div', { style: { flex: 1 } },
                React.createElement('div', { style: { color: '#e0e0e0', fontWeight: 'bold' } }, h.label),
                React.createElement('div', { style: { color: '#666', fontSize: '10px' } }, h.command),
              ),
              React.createElement('span', { style: keyBadgeStyle }, h.keys || '(nicht zugewiesen)'),
            )
          )
        ),

    // Hinweis
    React.createElement('div', {
      style: { color: '#666', fontSize: '10px', marginTop: '12px', padding: '6px', background: '#161b22', borderRadius: '3px' },
    }, 'Tastenkuerzel koennen in der OHIF-Konfiguration (hotkeys-Abschnitt in default.js) angepasst werden. Aenderungen erfordern einen Neustart des Viewers.'),
  );
}

// Hilfsfunktion: Command kategorisieren
// Wichtig: Spezifischere Keywords (layout, fit, reset) werden VOR
// dem generischen 'viewport' geprueft, da z.B. 'setViewportLayout'
// sowohl 'viewport' als auch 'layout' enthaelt.
function categorizeCommand(command) {
  const c = (command || '').toLowerCase();
  // Layout vor Viewport (setViewportLayout enthaelt beides)
  if (c.includes('layout') || c.includes('grid') || c.includes('split')) return 'Layout';
  // Navigation vor Viewport (fitToViewport, resetViewport)
  if (c.includes('zoom') || c.includes('pan') || c.includes('fit') || c.includes('reset')) return 'Navigation';
  // Jetzt die reinen Viewport-Aktionen
  if (c.includes('viewport') || c.includes('rotate') || c.includes('flip') || c.includes('invert')) return 'Viewport';
  if (c.includes('measure') || c.includes('annotation') || c.includes('roi') || c.includes('length') || c.includes('angle')) return 'Messung';
  if (c.includes('window') || c.includes('level') || c.includes('preset')) return 'Fensterung';
  if (c.includes('cine') || c.includes('play') || c.includes('pause') || c.includes('frame')) return 'Cine';
  if (c.includes('scroll') || c.includes('slice') || c.includes('next') || c.includes('prev')) return 'Scroll';
  if (c.includes('tool') || c.includes('select')) return 'Werkzeug';
  return 'Sonstige';
}

// Fallback: Standard-Hotkeys aus der Config
function getDefaultHotkeys() {
  return [
    { command: 'incrementActiveViewport', label: 'Naechster Viewport', keys: 'right', category: 'Viewport' },
    { command: 'decrementActiveViewport', label: 'Vorheriger Viewport', keys: 'left', category: 'Viewport' },
    { command: 'rotateViewportCW', label: 'Viewport rotieren (UZS)', keys: 'r', category: 'Viewport' },
    { command: 'flipViewportHorizontal', label: 'Horizontal spiegeln', keys: 'h', category: 'Viewport' },
    { command: 'invertViewport', label: 'Invertieren', keys: 'i', category: 'Fensterung' },
    { command: 'zoomIn', label: 'Zoom rein', keys: 'ctrl + +', category: 'Navigation' },
    { command: 'zoomOut', label: 'Zoom raus', keys: 'ctrl + -', category: 'Navigation' },
    { command: 'fitToViewport', label: 'An Viewport anpassen', keys: 'ctrl + 0', category: 'Navigation' },
    { command: 'resetViewport', label: 'Viewport zuruecksetzen', keys: 'ctrl + r', category: 'Navigation' },
    { command: 'scrollNextImage', label: 'Naechstes Bild', keys: 'down', category: 'Scroll' },
    { command: 'scrollPreviousImage', label: 'Vorheriges Bild', keys: 'up', category: 'Scroll' },
    { command: 'scrollFirstImage', label: 'Erstes Bild', keys: 'home', category: 'Scroll' },
    { command: 'scrollLastImage', label: 'Letztes Bild', keys: 'end', category: 'Scroll' },
    { command: 'playCine', label: 'Cine starten', keys: 'space', category: 'Cine' },
    { command: 'pauseCine', label: 'Cine pausieren', keys: 'space', category: 'Cine' },
    { command: 'setToolActive_Probe', label: 'Probe-Tool (Dichtewert)', keys: 'p', category: 'Werkzeug' },
    { command: 'setToolActive_Length', label: 'Laengenmessung', keys: 'l', category: 'Messung' },
    { command: 'setToolActive_Angle', label: 'Winkelmessung', keys: 'a', category: 'Messung' },
    { command: 'setToolActive_RectangleROI', label: 'Rechteck-ROI', keys: 'ctrl + r', category: 'Messung' },
    { command: 'setToolActive_EllipticalROI', label: 'Elliptische ROI', keys: 'ctrl + e', category: 'Messung' },
  ];
}

export default HotkeyHelpPanel;
