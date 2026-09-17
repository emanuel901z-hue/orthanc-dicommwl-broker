// DicomTagBrowserPanel - DICOM-Tag-Browser / Metadata-Inspector
//
// Zeigt alle DICOM-Tags einer Serie/Studie an, inkl. privater
// Carestream/Elscint-Tags (Site ID, Origin AE, Region, Station).
//
// Features:
//  - Auswahl zwischen aktiven DisplaySets (Serien)
//  - Suche/Filter nach Tag-Name oder Wert
//  - Gruppierung nach Tag-Gruppen (Patient, Study, Series, Image, Private)
//  - Anzeige von Standard- und Private-Tags
//  - Kopieren einzelner Werte

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';

// Bekannte private Carestream/Elscint Tags
const PRIVATE_TAGS_INFO = {
  '07A31015': 'Site ID (Carestream)',
  '07A51069': 'Origin AE Title (Carestream)',
  '07A11040': 'Region / Body Part (Elscint)',
};

// Wichtige Standard-Tags mit Beschreibung
const STANDARD_TAGS_INFO = {
  '00100010': 'Patient Name',
  '00100020': 'Patient ID',
  '00100030': 'Patient Birth Date',
  '00100040': 'Patient Sex',
  '00080050': 'Accession Number',
  '00080060': 'Modality',
  '00080070': 'Manufacturer',
  '00080080': 'Institution Name',
  '00080090': 'Referring Physician',
  '00081030': 'Study Description',
  '0008103E': 'Series Description',
  '00081010': 'Station Name',
  '00081090': 'Manufacturer Model Name',
  '00080020': 'Study Date',
  '00080030': 'Study Time',
  '00080021': 'Series Date',
  '00080031': 'Series Time',
  '0020000D': 'Study Instance UID',
  '0020000E': 'Series Instance UID',
  '00080018': 'SOP Instance UID',
  '00200011': 'Series Number',
  '00200013': 'Instance Number',
  '00280002': 'Samples Per Pixel',
  '00280010': 'Rows',
  '00280011': 'Columns',
  '00280030': 'Pixel Spacing',
  '00180050': 'Slice Thickness',
  '00180088': 'Spacing Between Slices',
  '00281050': 'Window Center',
  '00281051': 'Window Width',
  '00281040': 'Pixel Representation',
  '00280004': 'Photometric Interpretation',
  '00020010': 'Transfer Syntax UID',
};

// Tag-Gruppen fuer Filter
const TAG_GROUPS = {
  patient: { name: 'Patient', prefix: '0010' },
  study: { name: 'Studie', prefix: '0008' },
  series: { name: 'Serie', prefix: '0020' },
  image: { name: 'Bild', prefix: '0028' },
  acquisition: { name: 'Akquisition', prefix: '0018' },
  private: { name: 'Private Tags', prefix: '07A' },
  other: { name: 'Sonstige', prefix: null },
};

function getTagGroup(tagKey) {
  const prefix = tagKey.substring(0, 4);
  const prefix3 = tagKey.substring(0, 3);
  if (prefix === '0010') return 'patient';
  if (prefix === '0008') return 'study';
  if (prefix === '0020') return 'series';
  if (prefix === '0028') return 'image';
  if (prefix === '0018') return 'acquisition';
  if (prefix3 === '07A' || prefix3 === '07B' || prefix3 === '07C') return 'private';
  return 'other';
}

function formatTagValue(value) {
  if (value == null) return '';
  if (typeof value === 'object') {
    if (value.Alphabetic) return value.Alphabetic;
    if (Array.isArray(value)) return value.join(', ');
    return JSON.stringify(value);
  }
  return String(value);
}

function formatDicomDate(dateStr) {
  if (!dateStr || dateStr.length !== 8) return dateStr || '';
  return dateStr.substring(6, 8) + '.' + dateStr.substring(4, 6) + '.' + dateStr.substring(0, 4);
}

function DicomTagBrowserPanel({ servicesManager }) {
  const { displaySetService } = servicesManager?.services || {};

  const [displaySets, setDisplaySets] = useState([]);
  const [selectedDSUID, setSelectedDSUID] = useState(null);
  const [tags, setTags] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeGroup, setActiveGroup] = useState('all');
  const [copiedTag, setCopiedTag] = useState(null);

  // DisplaySets laden
  useEffect(() => {
    if (!displaySetService) return;
    const updateDisplaySets = () => {
      const ds = displaySetService.getActiveDisplaySets();
      setDisplaySets(ds || []);
      // Auto-select erste Serie nur wenn noch keine ausgewaehlt
      setSelectedDSUID(prev => {
        if (!prev && ds && ds.length > 0) return ds[0].displaySetInstanceUID;
        return prev;
      });
    };
    updateDisplaySets();
    const sub = displaySetService.subscribe?.(
      displaySetService.EVENTS?.DISPLAY_SETS_CHANGED,
      updateDisplaySets
    );
    return () => sub?.unsubscribe?.();
  }, [displaySetService]);

  // Tags fuer ausgewaehltes DisplaySet laden
  useEffect(() => {
    if (!displaySetService || !selectedDSUID) {
      setTags([]);
      return;
    }

    const ds = displaySetService.getDisplaySetByUID?.(selectedDSUID);
    if (!ds) {
      setTags([]);
      return;
    }

    // Instance-Metadata holen (erste Instanz reicht fuer Series-Level Tags)
    const instance = ds.instances?.[0] || ds.instance || {};
    const tagEntries = [];

    // Alle verfuegbaren Felder durchgehen
    for (const [key, value] of Object.entries(instance)) {
      // Interne Felder ueberspringen (mit _ oder $)
      if (key.startsWith('_') || key.startsWith('$') || key.startsWith('__')) continue;

      const tagInfo = STANDARD_TAGS_INFO[key] || PRIVATE_TAGS_INFO[key] || null;
      const group = getTagGroup(key);
      let displayValue = formatTagValue(value);

      // Datumsformatierung
      if (key.endsWith('Date') || key === '00080020' || key === '00080021' || key === '00100030') {
        displayValue = formatDicomDate(displayValue);
      }

      tagEntries.push({
        tag: key,
        name: tagInfo || key,
        value: displayValue,
        group,
        isPrivate: key.startsWith('07A') || key.startsWith('07B') || key.startsWith('07C'),
      });
    }

    // Nach Tag-Nummer sortieren
    tagEntries.sort((a, b) => a.tag.localeCompare(b.tag));
    setTags(tagEntries);
  }, [displaySetService, selectedDSUID]);

  // Gefilterte Tags
  const filteredTags = useMemo(() => {
    let result = tags;
    if (activeGroup !== 'all') {
      result = result.filter(t => t.group === activeGroup);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      result = result.filter(t =>
        t.tag.toLowerCase().includes(q) ||
        t.name.toLowerCase().includes(q) ||
        t.value.toLowerCase().includes(q)
      );
    }
    return result;
  }, [tags, activeGroup, searchQuery]);

  // Timeout-Ref fuer Copy-Reset (verhindert Memory Leak bei Unmount)
  const copyTimeoutRef = useRef(null);
  useEffect(() => () => { if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current); }, []);

  // Wert kopieren
  const copyValue = useCallback((tag, value) => {
    try {
      navigator.clipboard?.writeText(value);
      setCopiedTag(tag);
      if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current);
      copyTimeoutRef.current = setTimeout(() => setCopiedTag(null), 1500);
    } catch (e) {
      // Clipboard nicht verfuegbar
    }
  }, []);

  const selectedDS = displaySets.find(ds => ds.displaySetInstanceUID === selectedDSUID);

  const inputStyle = {
    width: '100%', padding: '4px 6px', marginBottom: '4px',
    border: '1px solid #555', borderRadius: '3px', background: '#1a1a2e',
    color: '#e0e0e0', fontSize: '12px',
  };
  const groupBtnStyle = (active) => ({
    padding: '3px 6px', border: 'none', borderRadius: '3px',
    background: active ? '#2a6cc7' : '#333', color: active ? '#fff' : '#999',
    cursor: 'pointer', fontSize: '10px', fontWeight: 'bold',
  });
  const tagRowStyle = (isPrivate) => ({
    padding: '3px 6px', borderBottom: '1px solid #2a2a3a',
    fontSize: '11px', display: 'flex', gap: '6px',
    background: isPrivate ? 'rgba(255, 215, 0, 0.05)' : 'transparent',
  });

  return React.createElement('div', {
    style: { padding: '8px', height: '100%', overflow: 'auto', background: '#0d1117' },
    'data-cy': 'dicom-tag-browser-panel',
  },
    // Header
    React.createElement('h3', {
      style: { color: '#e0e0e0', fontSize: '14px', margin: '0 0 8px 0', borderBottom: '1px solid #333', paddingBottom: '4px' },
    }, 'DICOM-Tag-Browser'),

    // DisplaySet-Auswahl
    React.createElement('label', { style: { display: 'block', fontSize: '11px', color: '#999', marginBottom: '2px' } }, 'Serie / DisplaySet'),
    React.createElement('select', {
      style: inputStyle,
      value: selectedDSUID || '',
      onChange: e => setSelectedDSUID(e.target.value),
    },
      displaySets.length === 0
        ? React.createElement('option', { value: '' }, '(keine Serie geladen)')
        : displaySets.map(ds =>
            React.createElement('option', {
              key: ds.displaySetInstanceUID,
              value: ds.displaySetInstanceUID,
            }, (ds.SeriesNumber || '?') + ': ' + (ds.SeriesDescription || ds.Modality || 'Unbekannt'))
          )
    ),

    // Serie-Info
    selectedDS && React.createElement('div', {
      style: { fontSize: '10px', color: '#666', marginBottom: '8px', padding: '4px', background: '#161b22', borderRadius: '3px' },
    },
      (selectedDS.Modality || '?') + ' | ' +
      (selectedDS.SeriesNumber || '?') + ' | ' +
      (dsInstancesCount(selectedDS)) + ' Bilder'
    ),

    // Suche
    React.createElement('input', {
      type: 'text', style: inputStyle, placeholder: 'Suche nach Tag-Name oder Wert...',
      value: searchQuery,
      onChange: e => setSearchQuery(e.target.value),
      'data-cy': 'tag-search',
    }),

    // Gruppen-Filter
    React.createElement('div', {
      style: { display: 'flex', gap: '2px', marginBottom: '8px', flexWrap: 'wrap' },
    },
      React.createElement('button', {
        style: groupBtnStyle(activeGroup === 'all'),
        onClick: () => setActiveGroup('all'),
      }, 'Alle (' + tags.length + ')'),
      Object.entries(TAG_GROUPS).map(([key, info]) => {
        const count = tags.filter(t => t.group === key).length;
        if (count === 0) return null;
        return React.createElement('button', {
          key: key,
          style: groupBtnStyle(activeGroup === key),
          onClick: () => setActiveGroup(key),
        }, info.name + ' (' + count + ')');
      }),
    ),

    // Tag-Liste
    filteredTags.length === 0
      ? React.createElement('div', {
          style: { color: '#666', fontSize: '12px', padding: '12px', textAlign: 'center' },
        }, tags.length === 0 ? 'Keine Tags verfuegbar.' : 'Keine Tags gefunden fuer Suche.')
      : React.createElement('div', {
          style: { background: '#161b22', borderRadius: '4px', maxHeight: '500px', overflow: 'auto' },
        },
          // Header
          React.createElement('div', {
            style: { display: 'flex', gap: '6px', padding: '4px 6px', background: '#1a2332', fontSize: '10px', color: '#999', fontWeight: 'bold', position: 'sticky', top: 0 },
          },
            React.createElement('span', { style: { width: '70px' } }, 'Tag'),
            React.createElement('span', { style: { flex: 1 } }, 'Name'),
            React.createElement('span', { style: { flex: 2 } }, 'Wert'),
          ),
          // Tags
          filteredTags.map((t, i) =>
            React.createElement('div', {
              key: t.tag || i,
              style: tagRowStyle(t.isPrivate),
              onClick: () => copyValue(t.tag, t.value),
              title: 'Klick zum Kopieren',
              'data-cy': 'dicom-tag-row',
            },
              React.createElement('span', {
                style: { width: '70px', color: t.isPrivate ? '#ffd700' : '#666', fontFamily: 'monospace', fontSize: '10px' },
              }, t.tag),
              React.createElement('span', {
                style: { flex: 1, color: '#999', fontSize: '10px' },
              }, t.name),
              React.createElement('span', {
                style: { flex: 2, color: copiedTag === t.tag ? '#4ec9b0' : '#e0e0e0', fontSize: '11px', wordBreak: 'break-all', cursor: 'pointer' },
              }, copiedTag === t.tag ? '(kopiert!)' : t.value),
            )
          )
        ),

    // Hinweis
    React.createElement('div', {
      style: { color: '#666', fontSize: '10px', marginTop: '8px', padding: '6px', background: '#161b22', borderRadius: '3px' },
    }, 'Private Tags (gelb markiert) sind Carestream/Elscint-spezifisch. Klicken Sie einen Tag an, um den Wert zu kopieren.'),
  );
}

// Hilfsfunktion: Anzahl Instanzen
function dsInstancesCount(ds) {
  if (ds.numInstances != null) return ds.numInstances;
  if (ds.instances) return ds.instances.length;
  return '?';
}

export default DicomTagBrowserPanel;
