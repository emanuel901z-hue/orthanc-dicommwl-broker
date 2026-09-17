// PacsBrowserPanel - PACS Study Browser mit Suche, Filtern und Favoriten
//
// Erlaubt die Suche nach Studien im PACS ueber QIDO-RS mit:
//  - Standard-Suchfelder: Patientenname, MRN, Accession, Datum, Modality, Beschreibung
//  - Erweiterte Filter (clientseitig nach WADO-Metadata): Site ID, Origin AE, Region, Station
//  - Favoriten (localStorage): Haeufig gesuchte Studien als Favorit markieren
//  - Zuletzt gesucht: Letzte Suchanfragen speichern und schnell wiederholen
//
// Gefundene Studien koennen per Klick in den Viewer geladen werden (loadStudy),
// wodurch sie im StudyBrowser erscheinen und per Drag&Drop in Viewports gezogen
// werden koennen. So lassen sich auch Studien anderer Patienten oder
// nicht verknuepfter Voruntersuchungen hinzufuegen.
//
// Private DICOM-Tags (Carestream/Elscint):
//  07A31015 [ST] - Site ID (z.B. "18A-ZNA", "18S-ST1")
//  07A51069 [AE] - Origin AE Title (z.B. "ct99", "CS7-0230")
//  07A11040 [CS] - Region/Body Part (z.B. "ABDOMEN", "HEAD", "KNEE")
//  00081010  [SH] - Station Name (Standard-Tag, z.B. "RUE-CT")

import React, { useState, useEffect, useCallback, useRef } from 'react';

// localStorage Keys
const FAVORITES_KEY = 'pacsBrowser.favorites';
const RECENT_SEARCHES_KEY = 'pacsBrowser.recentSearches';
const MAX_RECENT_SEARCHES = 10;
const MAX_RESULTS = 100;

// Private Carestream/Elscint Tags
const PRIVATE_TAGS = {
  siteId: '07A31015',
  originAE: '07A51069',
  region: '07A11040',
};

// Standard-Tags fuer erweiterte Anzeige
const STANDARD_TAGS = {
  stationName: '00081010',
  institution: '00080080',
  manufacturer: '00080070',
  model: '00081090',
};

// Hilfsfunktion: DICOM-Tag-Wert extrahieren
function getTagValue(metadata, tag) {
  const field = metadata[tag];
  if (!field || !field.Value || field.Value.length === 0) return null;
  const val = field.Value[0];
  if (typeof val === 'object' && val.Alphabetic) return val.Alphabetic;
  return String(val);
}

// Hilfsfunktion: Datum formatieren (YYYYMMDD -> DD.MM.YYYY)
function formatDate(dicomDate) {
  if (!dicomDate || dicomDate.length !== 8) return dicomDate || '';
  return dicomDate.substring(6, 8) + '.' + dicomDate.substring(4, 6) + '.' + dicomDate.substring(0, 4);
}

// Hilfsfunktion: Patientenname formatieren (DICOM PN -> "Nachname, Vorname")
function formatPN(pn) {
  if (!pn) return '';
  if (typeof pn === 'object' && pn.Alphabetic) pn = pn.Alphabetic;
  // DICOM PN Format: "Nachname^Vorname^Mittelname^Praefix^Suffix"
  const parts = String(pn).split('^');
  const nachname = parts[0] || '';
  const vorname = parts[1] || '';
  if (vorname) return nachname + ', ' + vorname;
  return nachname;
}

// Hilfsfunktion: Normalisiert einen DICOM-Patientennamen fuer Vergleich
// "Mummelthei^Manuel" -> "mummelthei, manuel"
function normalizePN(pn) {
  if (!pn) return '';
  if (typeof pn === 'object' && pn.Alphabetic) pn = pn.Alphabetic;
  const parts = String(pn).split('^');
  const nachname = (parts[0] || '').trim();
  const vorname = (parts[1] || '').trim();
  return (vorname ? nachname + ', ' + vorname : nachname).toLowerCase();
}

// Hilfsfunktion: Relevanz-Score fuer ein einzelnes Feld
// Score: 100 = exakt, 80 = beginnt mit, 60 = enthaelt, 0 = kein Treffer
function fieldScore(fieldValue, query) {
  if (!fieldValue || !query) return 0;
  const fv = String(fieldValue).toLowerCase().trim();
  const q = String(query).toLowerCase().trim();
  if (!fv || !q) return 0;
  if (fv === q) return 100;
  if (fv.startsWith(q)) return 80;
  if (fv.includes(q)) return 60;
  // Fuzzy: Query-Wortbestandteile im Feld vorhanden
  const qParts = q.split(/[\s,]+/).filter(Boolean);
  if (qParts.length > 1) {
    let matched = 0;
    qParts.forEach(qp => { if (fv.includes(qp)) matched++; });
    if (matched === qParts.length) return 40;
    if (matched > 0) return 20;
  }
  return 0;
}

// Hilfsfunktion: Sortiert QIDO-Ergebnisse nach Relevanz
// Priorisiert: 1. Genauigkeit des Matches, 2. Datum (neueste zuerst)
function sortByRelevance(studies, searchForm) {
  const queries = {};
  if (searchForm.patientName?.trim()) queries.patientName = searchForm.patientName.trim();
  if (searchForm.patientId?.trim()) queries.patientId = searchForm.patientId.trim();
  if (searchForm.accessionNumber?.trim()) queries.accessionNumber = searchForm.accessionNumber.trim();
  if (searchForm.studyDescription?.trim()) queries.studyDescription = searchForm.studyDescription.trim();
  if (searchForm.modalities?.trim()) queries.modalities = searchForm.modalities.trim();

  const queryKeys = Object.keys(queries);
  if (queryKeys.length === 0) return studies;

  return studies.map(study => {
    let totalScore = 0;
    if (queries.patientName) {
      const pn = study.patientName || '';
      // Score gegen formatierten Namen und gegen rohen DICOM-Namen
      const score1 = fieldScore(formatPN(pn), queries.patientName);
      const score2 = fieldScore(normalizePN(pn), queries.patientName);
      const score3 = fieldScore(String(pn).replace(/\^/g, ' '), queries.patientName);
      totalScore += Math.max(score1, score2, score3);
    }
    if (queries.patientId) {
      totalScore += fieldScore(study.mrn || study.patientId || study.PatientID || '', queries.patientId);
    }
    if (queries.accessionNumber) {
      totalScore += fieldScore(study.accession || study.accessionNumber || study.AccessionNumber || '', queries.accessionNumber);
    }
    if (queries.studyDescription) {
      totalScore += fieldScore(study.description || study.studyDescription || study.StudyDescription || '', queries.studyDescription);
    }
    if (queries.modalities) {
      const mod = study.modalities || study.modalitiesInStudy || study.ModalitiesInStudy || '';
      totalScore += fieldScore(Array.isArray(mod) ? mod.join(',') : mod, queries.modalities);
    }
    return { study, score: totalScore };
  }).sort((a, b) => {
    // Primaer: nach Relevanz-Score absteigend
    if (b.score !== a.score) return b.score - a.score;
    // Sekundaer: nach Datum absteigend (neueste zuerst)
    const dateA = a.study.date || a.study.studyDate || a.study.StudyDate || '';
    const dateB = b.study.date || b.study.studyDate || b.study.StudyDate || '';
    return dateB.localeCompare(dateA);
  }).map(item => item.study);
}

// Hilfsfunktion: Favoriten aus localStorage laden
function loadFavorites() {
  try {
    const raw = localStorage.getItem(FAVORITES_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
}

// Hilfsfunktion: Favoriten in localStorage speichern
function saveFavorites(favorites) {
  try {
    localStorage.setItem(FAVORITES_KEY, JSON.stringify(favorites));
  } catch (e) { console.warn('[PacsBrowser] Favoriten konnten nicht gespeichert werden:', e); }
}

// Hilfsfunktion: Letzte Suchanfragen laden
function loadRecentSearches() {
  try {
    const raw = localStorage.getItem(RECENT_SEARCHES_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
}

// Hilfsfunktion: Letzte Suchanfragen speichern
function saveRecentSearches(searches) {
  try {
    localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(searches.slice(0, MAX_RECENT_SEARCHES)));
  } catch (e) { console.warn('[PacsBrowser] Suchverlauf konnte nicht gespeichert werden:', e); }
}

function PacsBrowserPanel({ servicesManager, commandsManager, extensionManager }) {
  // extensionManager wird als Prop vom Panel-Wrapper durchgereicht
  // (siehe getPanelModule.js). Er wird benoetigt, um die aktive
  // DataSource fuer QIDO/WADO-Anfragen zu ermitteln.
  const extensionMgr = extensionManager;

  // Such-Formular-State
  const [searchForm, setSearchForm] = useState({
    patientName: '',
    patientId: '',
    accessionNumber: '',
    studyDescription: '',
    modalities: '',
    startDate: '',
    endDate: '',
  });

  // Erweiterte Filter (clientseitig)
  const [advFilters, setAdvFilters] = useState({
    siteId: '',
    originAE: '',
    region: '',
    stationName: '',
  });

  // Ergebnisse und Status
  const [results, setResults] = useState([]);
  const [filteredResults, setFilteredResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isLoadingMetadata, setIsLoadingMetadata] = useState(false);
  const [searchError, setSearchError] = useState('');
  const [statusMsg, setStatusMsg] = useState('');
  const isMountedRef = useRef(true);
  useEffect(() => () => { isMountedRef.current = false; }, []);

  // Favoriten und Suchverlauf
  const [favorites, setFavorites] = useState(() => loadFavorites());
  const [recentSearches, setRecentSearches] = useState(() => loadRecentSearches());

  // Aktiver Tab: 'search' | 'loaded' | 'favorites' | 'recent'
  const [activeTab, setActiveTab] = useState('search');

  // Geladene Study-UIDs (um zu markieren, was schon im Viewer ist)
  const [loadedStudyUIDs, setLoadedStudyUIDs] = useState(new Set());
  // Geladene Studien mit Metadaten fuer den 'Geladen'-Tab
  const [loadedStudies, setLoadedStudies] = useState([]);
  const metadataCacheRef = useRef(new Map());
  const repeatSearchTimeoutRef = useRef(null);

  // Aktualisiere geladene Studien (UIDs + Metadaten)
  useEffect(() => {
    if (!servicesManager?.services?.displaySetService) return;
    let DicomMetadataStore;
    try {
      DicomMetadataStore = require('@ohif/core').DicomMetadataStore;
    } catch (e) {
      console.warn('[PacsBrowser] DicomMetadataStore nicht verfuegbar');
    }
    const updateLoaded = () => {
      const dss = servicesManager.services.displaySetService;
      const ds = dss.getActiveDisplaySets();
      const uids = new Set(ds.map(d => d.StudyInstanceUID));
      setLoadedStudyUIDs(uids);

      // Vollstaendige Studien-Info fuer den 'Geladen'-Tab aufbauen
      // Patientendaten kommen aus DicomMetadataStore, nicht aus DisplaySets
      const studiesMap = new Map();
      ds.forEach(d => {
        const uid = d.StudyInstanceUID;
        if (!uid) return;
        if (!studiesMap.has(uid)) {
          // Versuche Patientendaten aus DicomMetadataStore zu holen
          let patientName = '';
          let mrn = '';
          let accession = '';
          let patientBirthDate = '';
          let studyDate = '';
          let studyDescription = '';
          let modalities = '';

          if (DicomMetadataStore) {
            const study = DicomMetadataStore.getStudy(uid);
            if (study) {
              patientName = study.PatientName || '';
              mrn = study.PatientID || '';
              accession = study.AccessionNumber || '';
              studyDate = study.StudyDate || '';
              studyDescription = study.StudyDescription || '';
              modalities = (study.ModalitiesInStudy || []).join(', ') ||
                           (study.series || []).map(s => s.Modality).filter(Boolean).join(', ');
            }
          }

          // Fallback: versuche Patientendaten aus erstem DisplaySet
          if (!patientName) patientName = d.PatientName || '';
          if (!mrn) mrn = d.PatientID || '';
          if (!accession) accession = d.AccessionNumber || '';
          if (!studyDate) studyDate = d.StudyDate || '';
          if (!studyDescription) studyDescription = d.StudyDescription || '';
          if (!modalities) modalities = d.Modality || '';

          // Versuche PatientBirthDate aus Instanz-Metadaten
          if (DicomMetadataStore && !patientBirthDate) {
            const study = DicomMetadataStore.getStudy(uid);
            if (study && study.series && study.series.length > 0) {
              const firstSeries = study.series[0];
              if (firstSeries.instances && firstSeries.instances.length > 0) {
                patientBirthDate = firstSeries.instances[0].PatientBirthDate || '';
                // Wenn PatientName noch leer, versuche aus Instanz
                if (!patientName) patientName = firstSeries.instances[0].PatientName || '';
                if (!mrn) mrn = firstSeries.instances[0].PatientID || '';
                if (!accession) accession = firstSeries.instances[0].AccessionNumber || '';
                if (!studyDate) studyDate = firstSeries.instances[0].StudyDate || '';
                if (!studyDescription) studyDescription = firstSeries.instances[0].StudyDescription || '';
              }
            }
          }

          studiesMap.set(uid, {
            studyInstanceUid: uid,
            description: studyDescription,
            date: studyDate,
            modalities: modalities,
            patientName: patientName,
            mrn: mrn,
            accession: accession,
            patientBirthDate: patientBirthDate,
            numSeries: 0,
            numInstances: 0,
          });
        }
        const info = studiesMap.get(uid);
        info.numSeries++;
        info.numInstances += d.numInstances || 0;
      });
      setLoadedStudies(Array.from(studiesMap.values()));
    };
    updateLoaded();
    const dss = servicesManager.services.displaySetService;
    const sub = dss.subscribe?.(dss.EVENTS?.DISPLAY_SETS_CHANGED, updateLoaded);
    const sub2 = dss.subscribe?.(dss.EVENTS?.DISPLAY_SETS_ADDED, updateLoaded);
    return () => { sub?.unsubscribe?.(); sub2?.unsubscribe?.(); };
  }, [servicesManager]);

  // QIDO-Suche ausfuehren
  const performSearch = useCallback(async () => {
    if (!extensionMgr) {
      setSearchError('ExtensionManager nicht verfuegbar');
      return;
    }

    setIsSearching(true);
    setSearchError('');
    setStatusMsg('Suche im PACS...');
    setResults([]);
    setFilteredResults([]);

    try {
      const dataSources = extensionMgr?.getActiveDataSource?.();
      const dataSource = dataSources && dataSources.length > 0 ? dataSources[0] : null;
      if (!dataSource || !dataSource.query || !dataSource.query.studies) {
        throw new Error('DataSource nicht verfuegbar');
      }

      // Such-Parameter fuer QIDO zusammenstellen
      const searchParams = {
        limit: MAX_RESULTS,
        disableWildcard: false,
      };
      if (searchForm.patientName.trim()) searchParams.patientName = searchForm.patientName.trim();
      if (searchForm.patientId.trim()) searchParams.patientId = searchForm.patientId.trim();
      if (searchForm.accessionNumber.trim()) searchParams.accessionNumber = searchForm.accessionNumber.trim();
      if (searchForm.studyDescription.trim()) searchParams.studyDescription = searchForm.studyDescription.trim();
      if (searchForm.modalities.trim()) searchParams.modalitiesInStudy = searchForm.modalities.trim();
      if (searchForm.startDate) {
        searchParams.startDate = searchForm.startDate.replace(/-/g, '');
      }
      if (searchForm.endDate) {
        searchParams.endDate = searchForm.endDate.replace(/-/g, '');
      }

      // Pruefe ob mindestens ein Suchkriterium angegeben ist
      const hasCriteria = Object.values(searchParams).some(v => v && v !== MAX_RESULTS && v !== false);
      if (!hasCriteria) {
        setSearchError('Bitte mindestens ein Suchkriterium angeben');
        setIsSearching(false);
        setStatusMsg('');
        return;
      }

      // QIDO-Suche ausfuehren
      const rawStudies = await dataSource.query.studies.search(searchParams);

      if (!rawStudies || rawStudies.length === 0) {
        setStatusMsg('Keine Studien gefunden');
        setResults([]);
        setFilteredResults([]);
      } else {
        // Ergebnisse nach Relevanz sortieren (exakte Treffer oben)
        const studies = sortByRelevance(rawStudies, searchForm);
        setStatusMsg(studies.length + ' Studie(n) gefunden');
        setResults(studies);
        setFilteredResults(studies);

        // Suchanfrage im Verlauf speichern
        const searchEntry = {
          params: { ...searchForm },
          timestamp: new Date().toISOString(),
          resultCount: studies.length,
        };
        const newRecent = [searchEntry, ...recentSearches.filter(
          r => JSON.stringify(r.params) !== JSON.stringify(searchEntry.params)
        )].slice(0, MAX_RECENT_SEARCHES);
        setRecentSearches(newRecent);
        saveRecentSearches(newRecent);

        // WADO-Metadata fuer private Tags asynchron laden
        loadMetadataForResults(studies, dataSource);
      }
    } catch (err) {
      console.error('[PacsBrowser] Suchfehler:', err);
      setSearchError('Suchfehler: ' + (err.message || 'Unbekannter Fehler'));
      setStatusMsg('');
    } finally {
      setIsSearching(false);
    }
  }, [extensionMgr, searchForm, recentSearches]);

  // WADO-Metadata fuer private Tags laden (asynchron, nicht-blockierend)
  const loadMetadataForResults = useCallback(async (studies, dataSource) => {
    if (!studies || !Array.isArray(studies)) return;
    setIsLoadingMetadata(true);
    const cache = metadataCacheRef.current;

    for (const study of studies.slice(0, 50)) { // Max 50 Studien Metadata laden
      if (!isMountedRef.current) return;
      const uid = study.studyInstanceUid || study.StudyInstanceUID;
      if (!uid || cache.has(uid)) continue;

      try {
        // WADO-Metadata abrufen (erste Instanz reicht fuer Study-Level Tags)
        const metadata = await dataSource.retrieve.series.metadata({
          studyInstanceUID: uid,
          seriesInstanceUID: null,
        });

        if (metadata && metadata.length > 0) {
          const inst = metadata[0];
          const enriched = {
            siteId: getTagValue(inst, PRIVATE_TAGS.siteId),
            originAE: getTagValue(inst, PRIVATE_TAGS.originAE),
            region: getTagValue(inst, PRIVATE_TAGS.region),
            stationName: getTagValue(inst, STANDARD_TAGS.stationName),
            institution: getTagValue(inst, STANDARD_TAGS.institution),
            manufacturer: getTagValue(inst, STANDARD_TAGS.manufacturer),
            model: getTagValue(inst, STANDARD_TAGS.model),
          };
          cache.set(uid, enriched);
        }
      } catch (err) {
        // Metadata-Laden fehlgeschlagen - nicht kritisch
        cache.set(uid, {});
      }
    }

    if (!isMountedRef.current) return;
    // Ergebnisse mit Metadata anreichern und Filter anwenden
    setResults(prev => prev.map(s => {
      const uid = s.studyInstanceUid || s.StudyInstanceUID;
      const meta = cache.get(uid) || {};
      return { ...s, _meta: meta };
    }));

    setIsLoadingMetadata(false);
    setStatusMsg(prev => prev + ' (Metadata geladen)');
  }, []);

  // Erweiterte Filter anwenden (clientseitig)
  useEffect(() => {
    if (!results.length) {
      setFilteredResults([]);
      return;
    }

    let filtered = results;

    if (advFilters.siteId.trim()) {
      filtered = filtered.filter(s => {
        const val = s._meta?.siteId || '';
        return val.toLowerCase().includes(advFilters.siteId.trim().toLowerCase());
      });
    }
    if (advFilters.originAE.trim()) {
      filtered = filtered.filter(s => {
        const val = s._meta?.originAE || '';
        return val.toLowerCase().includes(advFilters.originAE.trim().toLowerCase());
      });
    }
    if (advFilters.region.trim()) {
      filtered = filtered.filter(s => {
        const val = s._meta?.region || '';
        return val.toLowerCase().includes(advFilters.region.trim().toLowerCase());
      });
    }
    if (advFilters.stationName.trim()) {
      filtered = filtered.filter(s => {
        const val = s._meta?.stationName || '';
        return val.toLowerCase().includes(advFilters.stationName.trim().toLowerCase());
      });
    }

    setFilteredResults(filtered);
  }, [results, advFilters]);

  // Studie in den Viewer laden
  const loadStudy = useCallback(async (studyInstanceUID) => {
    if (!studyInstanceUID) return;
    setStatusMsg('Studie wird geladen: ' + studyInstanceUID.substring(0, 30) + '...');

    try {
      // Verwende den loadStudy-Command aus dem default-Extension-Command-Module
      if (commandsManager) {
        await commandsManager.runCommand('loadStudy', { StudyInstanceUID: studyInstanceUID });
        setStatusMsg('Studie geladen und im StudyBrowser verfuegbar');
      } else {
        throw new Error('CommandsManager nicht verfuegbar');
      }
    } catch (err) {
      console.error('[PacsBrowser] loadStudy-Fehler:', err);
      setSearchError('Studie konnte nicht geladen werden: ' + (err.message || 'Unbekannt'));
      setStatusMsg('');
    }
  }, [commandsManager]);

  // Studie als Favorit hinzufuegen/entfernen
  const toggleFavorite = useCallback((study) => {
    const uid = study.studyInstanceUid || study.StudyInstanceUID;
    const exists = favorites.find(f => f.uid === uid);
    let newFavs;
    if (exists) {
      newFavs = favorites.filter(f => f.uid !== uid);
    } else {
      newFavs = [...favorites, {
        uid,
        patientName: study.patientName || '',
        mrn: study.mrn || '',
        description: study.description || '',
        date: study.date || '',
        modalities: study.modalities || '',
        accession: study.accession || '',
        addedAt: new Date().toISOString(),
      }];
    }
    setFavorites(newFavs);
    saveFavorites(newFavs);
  }, [favorites]);

  // Pruefe ob Studie ein Favorit ist
  const isFavorite = useCallback((uid) => {
    return favorites.some(f => f.uid === uid);
  }, [favorites]);

  // Favorit entfernen
  const removeFavorite = useCallback((uid) => {
    const newFavs = favorites.filter(f => f.uid !== uid);
    setFavorites(newFavs);
    saveFavorites(newFavs);
  }, [favorites]);

  // Letzte Suchanfrage wiederholen (inkl. automatischer Suche)
  const repeatSearch = useCallback((searchEntry) => {
    setSearchForm(searchEntry.params);
    setActiveTab('search');
    // Suche wird automatisch durch performSearch getriggert,
    // nachdem die Form-Daten aktualisiert wurden.
    // Da React State-Updates asynchron sind, rufen wir performSearch
    // direkt mit den params auf, statt auf State-Aenderung zu warten.
    // Timeout-ID in useRef speichern fuer Cleanup bei Unmount.
    if (repeatSearchTimeoutRef.current) {
      clearTimeout(repeatSearchTimeoutRef.current);
    }
    repeatSearchTimeoutRef.current = setTimeout(() => {
      const performSearchWithParams = async () => {
        if (!extensionMgr) return;
        setIsSearching(true);
        setSearchError('');
        setStatusMsg('Suche im PACS...');
        setResults([]);
        setFilteredResults([]);
        try {
          const dataSources = extensionMgr?.getActiveDataSource?.();
          const dataSource = dataSources && dataSources.length > 0 ? dataSources[0] : null;
          if (!dataSource || !dataSource.query || !dataSource.query.studies) {
            throw new Error('DataSource nicht verfuegbar');
          }
          const searchParams = { limit: MAX_RESULTS, disableWildcard: false };
          const p = searchEntry.params;
          if (p.patientName?.trim()) searchParams.patientName = p.patientName.trim();
          if (p.patientId?.trim()) searchParams.patientId = p.patientId.trim();
          if (p.accessionNumber?.trim()) searchParams.accessionNumber = p.accessionNumber.trim();
          if (p.studyDescription?.trim()) searchParams.studyDescription = p.studyDescription.trim();
          if (p.modalities?.trim()) searchParams.modalitiesInStudy = p.modalities.trim();
          if (p.startDate) searchParams.startDate = p.startDate.replace(/-/g, '');
          if (p.endDate) searchParams.endDate = p.endDate.replace(/-/g, '');

          const rawStudies = await dataSource.query.studies.search(searchParams);
          if (!rawStudies || rawStudies.length === 0) {
            setStatusMsg('Keine Studien gefunden');
            setResults([]);
            setFilteredResults([]);
          } else {
            const studies = sortByRelevance(rawStudies, p);
            setStatusMsg(studies.length + ' Studie(n) gefunden');
            setResults(studies);
            setFilteredResults(studies);
            loadMetadataForResults(studies, dataSource);
          }
        } catch (err) {
          console.error('[PacsBrowser] repeatSearch-Fehler:', err);
          setSearchError('Suchfehler: ' + (err.message || 'Unbekannter Fehler'));
          setStatusMsg('');
        } finally {
          setIsSearching(false);
        }
      };
      performSearchWithParams();
    }, 100);
  }, [extensionMgr, loadMetadataForResults]);

  // Cleanup: Timeout bei Unmount abbrechen.
  useEffect(() => {
    return () => {
      if (repeatSearchTimeoutRef.current) {
        clearTimeout(repeatSearchTimeoutRef.current);
      }
    };
  }, []);

  // Letzte Suchanfrage loeschen
  const removeRecentSearch = useCallback((index) => {
    const newRecent = recentSearches.filter((_, i) => i !== index);
    setRecentSearches(newRecent);
    saveRecentSearches(newRecent);
  }, [recentSearches]);

  // Formular zuruecksetzen
  const resetForm = useCallback(() => {
    setSearchForm({
      patientName: '', patientId: '', accessionNumber: '',
      studyDescription: '', modalities: '', startDate: '', endDate: '',
    });
    setAdvFilters({ siteId: '', originAE: '', region: '', stationName: '' });
    setResults([]);
    setFilteredResults([]);
    setSearchError('');
    setStatusMsg('');
  }, []);

  // Input-Change-Handler
  const handleSearchChange = (field, value) => {
    setSearchForm(prev => ({ ...prev, [field]: value }));
  };
  const handleFilterChange = (field, value) => {
    setAdvFilters(prev => ({ ...prev, [field]: value }));
  };

  // Styles
  const inputStyle = {
    width: '100%', padding: '4px 6px', marginBottom: '4px',
    border: '1px solid #555', borderRadius: '3px', background: '#1a1a2e',
    color: '#e0e0e0', fontSize: '12px',
  };
  const labelStyle = {
    display: 'block', fontSize: '11px', color: '#999', marginBottom: '2px', marginTop: '6px',
  };
  const btnStyle = {
    padding: '6px 12px', border: 'none', borderRadius: '3px',
    cursor: 'pointer', fontSize: '12px', fontWeight: 'bold',
  };
  const tabBtnStyle = (active) => ({
    ...btnStyle,
    background: active ? '#2a6cc7' : '#333',
    color: active ? '#fff' : '#999',
    flex: 1,
  });
  const resultRowStyle = (isLoaded) => ({
    padding: '6px 8px', borderBottom: '1px solid #333',
    background: isLoaded ? 'rgba(42, 108, 199, 0.15)' : 'transparent',
    cursor: 'pointer', fontSize: '11px',
  });
  const favBtnStyle = (isFav) => ({
    ...btnStyle, background: 'transparent', border: 'none',
    color: isFav ? '#ffd700' : '#666', fontSize: '14px', padding: '0 4px',
    cursor: 'pointer',
  });

  return React.createElement('div', {
    style: { padding: '8px', height: '100%', overflow: 'auto', background: '#0d1117' },
    'data-cy': 'pacs-browser-panel',
  },
    // Header
    React.createElement('h3', {
      style: { color: '#e0e0e0', fontSize: '14px', margin: '0 0 8px 0', borderBottom: '1px solid #333', paddingBottom: '4px' },
    }, 'PACS Browser'),

    // Tab-Navigation
    React.createElement('div', { style: { display: 'flex', gap: '2px', marginBottom: '8px' } },
      React.createElement('button', {
        style: tabBtnStyle(activeTab === 'search'),
        onClick: () => setActiveTab('search'),
      }, 'Suche'),
      React.createElement('button', {
        style: tabBtnStyle(activeTab === 'loaded'),
        onClick: () => setActiveTab('loaded'),
      }, 'Geladen (' + loadedStudies.length + ')'),
      React.createElement('button', {
        style: tabBtnStyle(activeTab === 'favorites'),
        onClick: () => setActiveTab('favorites'),
      }, 'Favoriten (' + favorites.length + ')'),
      React.createElement('button', {
        style: tabBtnStyle(activeTab === 'recent'),
        onClick: () => setActiveTab('recent'),
      }, 'Verlauf (' + recentSearches.length + ')'),
    ),

    // === TAB: SUCHE ===
    activeTab === 'search' && React.createElement('div', null,
      // Such-Formular
      React.createElement('div', { style: { background: '#161b22', padding: '8px', borderRadius: '4px' } },
        React.createElement('label', { style: labelStyle }, 'Patientenname'),
        React.createElement('input', {
          type: 'text', style: inputStyle, placeholder: 'z.B. Mueller*',
          value: searchForm.patientName,
          onChange: e => handleSearchChange('patientName', e.target.value),
          onKeyDown: e => { if (e.key === 'Enter') performSearch(); },
        }),
        React.createElement('label', { style: labelStyle }, 'MRN / Patienten-ID'),
        React.createElement('input', {
          type: 'text', style: inputStyle, placeholder: 'z.B. 1063726',
          value: searchForm.patientId,
          onChange: e => handleSearchChange('patientId', e.target.value),
          onKeyDown: e => { if (e.key === 'Enter') performSearch(); },
        }),
        React.createElement('label', { style: labelStyle }, 'Accession Number'),
        React.createElement('input', {
          type: 'text', style: inputStyle, placeholder: 'z.B. U-ID10684224',
          value: searchForm.accessionNumber,
          onChange: e => handleSearchChange('accessionNumber', e.target.value),
          onKeyDown: e => { if (e.key === 'Enter') performSearch(); },
        }),
        React.createElement('label', { style: labelStyle }, 'Studienbeschreibung'),
        React.createElement('input', {
          type: 'text', style: inputStyle, placeholder: 'z.B. CT*Abdomen*',
          value: searchForm.studyDescription,
          onChange: e => handleSearchChange('studyDescription', e.target.value),
          onKeyDown: e => { if (e.key === 'Enter') performSearch(); },
        }),
        React.createElement('div', { style: { display: 'flex', gap: '4px' } },
          React.createElement('div', { style: { flex: 1 } },
            React.createElement('label', { style: labelStyle }, 'Modality'),
            React.createElement('input', {
              type: 'text', style: inputStyle, placeholder: 'CT, MR, DX',
              value: searchForm.modalities,
              onChange: e => handleSearchChange('modalities', e.target.value),
              onKeyDown: e => { if (e.key === 'Enter') performSearch(); },
            }),
          ),
          React.createElement('div', { style: { flex: 1 } },
            React.createElement('label', { style: labelStyle }, 'Datum von'),
            React.createElement('input', {
              type: 'date', style: inputStyle,
              value: searchForm.startDate,
              onChange: e => handleSearchChange('startDate', e.target.value),
            }),
          ),
          React.createElement('div', { style: { flex: 1 } },
            React.createElement('label', { style: labelStyle }, 'bis'),
            React.createElement('input', {
              type: 'date', style: inputStyle,
              value: searchForm.endDate,
              onChange: e => handleSearchChange('endDate', e.target.value),
            }),
          ),
        ),

        // Such- und Reset-Buttons
        React.createElement('div', { style: { display: 'flex', gap: '4px', marginTop: '8px' } },
          React.createElement('button', {
            style: { ...btnStyle, background: '#2a6cc7', color: '#fff', flex: 1 },
            onClick: performSearch,
            disabled: isSearching,
          }, isSearching ? 'Suche...' : 'Suchen'),
          React.createElement('button', {
            style: { ...btnStyle, background: '#444', color: '#ccc' },
            onClick: resetForm,
          }, 'Zuruecksetzen'),
        ),
      ),

      // Erweiterte Filter (clientseitig, nach WADO-Metadata)
      results.length > 0 && React.createElement('details', {
        style: { marginTop: '8px', padding: '6px', background: '#161b22', borderRadius: '4px' },
      },
        React.createElement('summary', {
          style: { cursor: 'pointer', color: '#999', fontSize: '11px', fontWeight: 'bold' },
        }, 'Erweiterte Filter (Carestream Private Tags)' + (isLoadingMetadata ? ' [lade Metadata...]' : '')),
        React.createElement('div', { style: { marginTop: '6px' } },
          React.createElement('label', { style: labelStyle }, 'Site ID (07A31015)'),
          React.createElement('input', {
            type: 'text', style: inputStyle, placeholder: 'z.B. 18A-ZNA',
            value: advFilters.siteId,
            onChange: e => handleFilterChange('siteId', e.target.value),
          }),
          React.createElement('label', { style: labelStyle }, 'Origin AE Title (07A51069)'),
          React.createElement('input', {
            type: 'text', style: inputStyle, placeholder: 'z.B. ct99',
            value: advFilters.originAE,
            onChange: e => handleFilterChange('originAE', e.target.value),
          }),
          React.createElement('label', { style: labelStyle }, 'Region / Body Part (07A11040)'),
          React.createElement('input', {
            type: 'text', style: inputStyle, placeholder: 'z.B. ABDOMEN',
            value: advFilters.region,
            onChange: e => handleFilterChange('region', e.target.value),
          }),
          React.createElement('label', { style: labelStyle }, 'Station Name (00081010)'),
          React.createElement('input', {
            type: 'text', style: inputStyle, placeholder: 'z.B. RUE-CT',
            value: advFilters.stationName,
            onChange: e => handleFilterChange('stationName', e.target.value),
          }),
        ),
      ),

      // Fehlermeldung
      searchError && React.createElement('div', {
        style: { color: '#ff6b6b', fontSize: '11px', padding: '6px', marginTop: '4px', background: '#2a1515', borderRadius: '3px' },
      }, searchError),

      // Status
      statusMsg && React.createElement('div', {
        style: { color: '#4ec9b0', fontSize: '11px', padding: '4px', marginTop: '4px' },
      }, statusMsg),

      // Ergebnisliste
      filteredResults.length > 0 && React.createElement('div', {
        style: { marginTop: '8px', maxHeight: '400px', overflow: 'auto' },
      },
        React.createElement('div', {
          style: { color: '#999', fontSize: '11px', marginBottom: '4px' },
        }, filteredResults.length + ' Studie(n)' + (filteredResults.length !== results.length ? ' (gefiltert von ' + results.length + ')' : '') + ' - Klick zum Laden:'),
        filteredResults.map((study, i) => {
          const uid = study.studyInstanceUid || study.StudyInstanceUID;
          const isLoaded = loadedStudyUIDs.has(uid);
          const isFav = isFavorite(uid);
          const meta = study._meta || {};
          return React.createElement('div', {
            key: uid || i,
            style: resultRowStyle(isLoaded),
            onClick: () => loadStudy(uid),
            'data-cy': 'pacs-browser-result',
          },
            // Favorit-Button
            React.createElement('button', {
              style: favBtnStyle(isFav),
              onClick: e => { e.stopPropagation(); toggleFavorite(study); },
              title: isFav ? 'Aus Favoriten entfernen' : 'Als Favorit hinzufuegen',
            }, isFav ? '\u2605' : '\u2606'),
            // Studien-Info
            React.createElement('div', { style: { display: 'inline-block', width: 'calc(100% - 24px)', verticalAlign: 'top' } },
              React.createElement('div', { style: { fontWeight: 'bold', color: '#e0e0e0' } },
                formatDate(study.date) + ' - ' + (study.description || '(keine Beschreibung)')
              ),
              React.createElement('div', { style: { color: '#999' } },
                (study.modalities || '?') + ' | ' + formatPN(study.patientName) + ' | MRN: ' + (study.mrn || '?') + ' | Acc: ' + (study.accession || '?')
              ),
              // Private Tags anzeigen (wenn verfuegbar)
              (meta.siteId || meta.originAE || meta.region || meta.stationName) && React.createElement('div', {
                style: { color: '#666', fontSize: '10px', marginTop: '2px' },
              },
                [
                  meta.siteId && 'Site: ' + meta.siteId,
                  meta.originAE && 'AE: ' + meta.originAE,
                  meta.region && 'Region: ' + meta.region,
                  meta.stationName && 'Station: ' + meta.stationName,
                ].filter(Boolean).join(' | ')
              ),
              // Status: bereits geladen
              isLoaded && React.createElement('div', {
                style: { color: '#4ec9b0', fontSize: '10px', marginTop: '2px' },
              }, '\u2713 Im Viewer geladen'),
            ),
          );
        }),
      ),
    ),

    // === TAB: GELADEN ===
    activeTab === 'loaded' && React.createElement('div', null,
      loadedStudies.length === 0
        ? React.createElement('div', {
            style: { color: '#666', fontSize: '12px', padding: '16px', textAlign: 'center' },
          }, 'Keine Studien im Viewer geladen.\nVerwenden Sie die Suche, um Studien zu finden und zu laden.')
        : React.createElement('div', null,
            React.createElement('div', {
              style: { color: '#999', fontSize: '11px', marginBottom: '8px' },
            }, loadedStudies.length + ' Studie(n) im Viewer - mit Patientendaten:'),
            loadedStudies.map((study, i) => {
              const patName = formatPN(study.patientName) || '(unbekannt)';
              const mrn = study.mrn || '(unbekannt)';
              const acc = study.accession || '(unbekannt)';
              const mod = study.modalities || '(unbekannt)';
              const desc = study.description || '(keine Beschreibung)';
              const dateStr = study.date ? formatDate(study.date) : '(kein Datum)';
              const birthStr = study.patientBirthDate ? ' | Geb: ' + formatDate(study.patientBirthDate) : '';
              return React.createElement('div', {
                key: study.studyInstanceUid || i,
                style: { ...resultRowStyle(true), borderBottom: '1px solid #333', display: 'block' },
                'data-cy': 'pacs-browser-loaded',
              },
                React.createElement('div', { style: { width: '100%' } },
                  // Studien-Datum + Beschreibung (fett)
                  React.createElement('div', { style: { fontWeight: 'bold', color: '#4ec9b0' } },
                    dateStr + ' - ' + desc
                  ),
                  // Patientendaten: Name | MRN | Geburtstag
                  React.createElement('div', { style: { color: '#e0e0e0', marginTop: '3px' } },
                    patName + ' | MRN: ' + mrn + birthStr
                  ),
                  // Studien-Details: Modality | Accession | Serien/Bilder
                  React.createElement('div', { style: { color: '#999', marginTop: '1px' } },
                    mod + ' | Acc: ' + acc +
                    ' | ' + study.numSeries + ' Serie(n), ' + study.numInstances + ' Bilder'
                  ),
                ),
              );
            }),
          ),
    ),

    // === TAB: FAVORITEN ===
    activeTab === 'favorites' && React.createElement('div', null,
      favorites.length === 0
        ? React.createElement('div', {
            style: { color: '#666', fontSize: '12px', padding: '16px', textAlign: 'center' },
          }, 'Keine Favoriten vorhanden.\nKlicken Sie auf das Stern-Symbol bei einer Studie, um sie als Favorit zu markieren.')
        : React.createElement('div', null,
            React.createElement('div', {
              style: { color: '#999', fontSize: '11px', marginBottom: '8px' },
            }, favorites.length + ' Favorit(en) - Klick zum Laden:'),
            favorites.map((fav, i) => {
              const isLoaded = loadedStudyUIDs.has(fav.uid);
              return React.createElement('div', {
                key: fav.uid || i,
                style: resultRowStyle(isLoaded),
                onClick: () => loadStudy(fav.uid),
                'data-cy': 'pacs-browser-favorite',
              },
                React.createElement('button', {
                  style: { ...btnStyle, background: 'transparent', border: 'none', color: '#ff6b6b', fontSize: '14px', padding: '0 4px', cursor: 'pointer' },
                  onClick: e => { e.stopPropagation(); removeFavorite(fav.uid); },
                  title: 'Favorit entfernen',
                }, '\u2715'),
                React.createElement('div', { style: { display: 'inline-block', width: 'calc(100% - 24px)', verticalAlign: 'top' } },
                  React.createElement('div', { style: { fontWeight: 'bold', color: '#ffd700' } },
                    '\u2605 ' + formatDate(fav.date) + ' - ' + (fav.description || '(keine Beschreibung)')
                  ),
                  React.createElement('div', { style: { color: '#999' } },
                    (fav.modalities || '?') + ' | ' + formatPN(fav.patientName) + ' | MRN: ' + (fav.mrn || '?')
                  ),
                  isLoaded && React.createElement('div', {
                    style: { color: '#4ec9b0', fontSize: '10px', marginTop: '2px' },
                  }, '\u2713 Im Viewer geladen'),
                ),
              );
            }),
          ),
    ),

    // === TAB: VERLAUF ===
    activeTab === 'recent' && React.createElement('div', null,
      recentSearches.length === 0
        ? React.createElement('div', {
            style: { color: '#666', fontSize: '12px', padding: '16px', textAlign: 'center' },
          }, 'Keine Suchanfragen im Verlauf.')
        : React.createElement('div', null,
            React.createElement('div', {
              style: { color: '#999', fontSize: '11px', marginBottom: '8px' },
            }, 'Letzte Suchanfragen - Klick zum Wiederholen:'),
            recentSearches.map((entry, i) => {
              const params = entry.params;
              const summary = Object.entries(params).filter(([, v]) => v).map(([k, v]) => k + '=' + v).join(', ') || '(leere Suche)';
              const date = new Date(entry.timestamp);
              return React.createElement('div', {
                key: entry.timestamp || i,
                style: { ...resultRowStyle(false), display: 'flex', alignItems: 'center' },
                onClick: () => repeatSearch(entry),
                'data-cy': 'pacs-browser-recent',
              },
                React.createElement('div', { style: { flex: 1 } },
                  React.createElement('div', { style: { color: '#e0e0e0' } }, summary),
                  React.createElement('div', { style: { color: '#666', fontSize: '10px' } },
                    date.toLocaleString('de-DE') + ' | ' + (entry.resultCount || 0) + ' Ergebnisse'
                  ),
                ),
                React.createElement('button', {
                  style: { ...btnStyle, background: 'transparent', border: 'none', color: '#ff6b6b', fontSize: '14px', padding: '0 4px', cursor: 'pointer' },
                  onClick: e => { e.stopPropagation(); removeRecentSearch(i); },
                  title: 'Aus Verlauf entfernen',
                }, '\u2715'),
              );
            }),
          ),
    ),
  );
}

export default PacsBrowserPanel;
