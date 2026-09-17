// Panel-Module: Registriert alle Panels der Extension in der
// OHIF-Seitenleiste.
//
// OHIF v3 reicht die Manager (servicesManager, commandsManager,
// extensionManager) an getPanelModule als Argumente. Die Panel-
// Komponenten werden in Wrapper-Funktionen gepackt, damit diese
// Manager als Props an die Komponenten weitergegeben werden.
// (Siehe OHIF-Doku: platform/extensions/modules/panel)
//
// Registrierte Panels:
//   1. ticPanel             - Time-Intensity Curve (4D/dynamisch)
//   2. mismatchPanel        - Mismatch-Analyse (Subtraktion/Overlay)
//   3. vesselTrackingPanel  - Vessel Tracking (MIP/MPR)
//   4. pacsBrowserPanel     - PACS Browser (QIDO-Studiensuche)
//   5. wlPresetsPanel       - Fensterungs-Presets (W/L)
//   6. roiStatsPanel        - ROI-Statistiken / HU-Auslesung
//   7. dicomTagBrowserPanel - DICOM-Tag-Browser / Metadata-Inspector
//   8. studyComparePanel    - Studien-Vergleich / Viewport-Sync
//   9. cineNavPanel         - Cine / 4D-Navigation
//  10. measurementExportPanel - Messungs-Export (DICOM SR/CSV/JSON)
//  11. mprSlabPanel         - MPR / Slab / MIP Quick-Controls
//  12. hotkeyHelpPanel      - Tastenkuerzel-Uebersicht

import React from 'react';
import TICPanel from './panels/TICPanel.jsx';
import MismatchPanel from './panels/MismatchPanel.jsx';
import VesselTrackingPanel from './panels/VesselTrackingPanel.jsx';
import PacsBrowserPanel from './panels/PacsBrowserPanel.jsx';
import WindowLevelPresetsPanel from './panels/WindowLevelPresetsPanel.jsx';
import ROIStatsPanel from './panels/ROIStatsPanel.jsx';
import DicomTagBrowserPanel from './panels/DicomTagBrowserPanel.jsx';
import StudyComparePanel from './panels/StudyComparePanel.jsx';
import CineNavigationPanel from './panels/CineNavigationPanel.jsx';
import MeasurementExportPanel from './panels/MeasurementExportPanel.jsx';
import MPRSlabControlsPanel from './panels/MPRSlabControlsPanel.jsx';
import HotkeyHelpPanel from './panels/HotkeyHelpPanel.jsx';

// Error Boundary: Faengt Runtime-Fehler in Panels ab, sodass ein
// fehlerhaftes Panel nicht die gesamte OHIF-App zum Absturz bringt.
class PanelErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, errorInfo) {
    console.error('[PanelErrorBoundary]', this.props.panelName, error, errorInfo);
  }
  render() {
    if (this.state.hasError) {
      return React.createElement('div', {
        style: { padding: '12px', color: '#ff6b6b', fontSize: '12px' },
      },
        React.createElement('h4', null, 'Panel-Fehler: ' + (this.props.panelName || 'Unbekannt')),
        React.createElement('p', null, this.state.error?.message || 'Unbekannter Fehler'),
        React.createElement('button', {
          onClick: () => this.setState({ hasError: false, error: null }),
          style: { marginTop: '8px', padding: '4px 12px', cursor: 'pointer' },
        }, 'Erneut versuchen'),
      );
    }
    return this.props.children;
  }
}

function getPanelModule({ commandsManager, extensionManager, servicesManager }) {
  const wrap = (Component, panelName) => props =>
    React.createElement(PanelErrorBoundary, { panelName },
      React.createElement(Component, {
        servicesManager,
        commandsManager,
        extensionManager,
        ...props,
      })
    );

  return [
    {
      name: 'ticPanel',
      iconName: 'tab-4d',
      iconLabel: 'TIC',
      label: 'Time-Intensity Curve',
      component: wrap(TICPanel, "ticPanel"),
    },
    {
      name: 'mismatchPanel',
      iconName: 'actions-combine-subtract',
      iconLabel: 'Mismatch',
      label: 'Mismatch Analysis',
      component: wrap(MismatchPanel, "mismatchPanel"),
    },
    {
      name: 'vesselTrackingPanel',
      iconName: 'tab-segmentation',
      iconLabel: 'Vessels',
      label: 'Vessel Tracking',
      component: wrap(VesselTrackingPanel, "vesselTrackingPanel"),
    },
    {
      name: 'pacsBrowserPanel',
      iconName: 'tab-studies',
      iconLabel: 'PACS',
      label: 'PACS Browser',
      component: wrap(PacsBrowserPanel, "pacsBrowserPanel"),
    },
    {
      name: 'wlPresetsPanel',
      iconName: 'tool-window-level',
      iconLabel: 'W/L',
      label: 'Fensterungs-Presets',
      component: wrap(WindowLevelPresetsPanel, "wlPresetsPanel"),
    },
    {
      name: 'roiStatsPanel',
      iconName: 'tab-roi-threshold',
      iconLabel: 'ROI',
      label: 'ROI-Statistiken',
      component: wrap(ROIStatsPanel, "roiStatsPanel"),
    },
    {
      name: 'dicomTagBrowserPanel',
      iconName: 'dicom-tag-browser',
      iconLabel: 'Tags',
      label: 'DICOM-Tag-Browser',
      component: wrap(DicomTagBrowserPanel, "dicomTagBrowserPanel"),
    },
    {
      name: 'studyComparePanel',
      iconName: 'tool-stack-image-sync',
      iconLabel: 'Sync',
      label: 'Studien-Vergleich',
      component: wrap(StudyComparePanel, "studyComparePanel"),
    },
    {
      name: 'cineNavPanel',
      iconName: 'tool-cine',
      iconLabel: 'Cine',
      label: 'Cine / 4D-Navigation',
      component: wrap(CineNavigationPanel, "cineNavPanel"),
    },
    {
      name: 'measurementExportPanel',
      iconName: 'Export',
      iconLabel: 'Export',
      label: 'Messungs-Export',
      component: wrap(MeasurementExportPanel, "measurementExportPanel"),
    },
    {
      name: 'mprSlabPanel',
      iconName: 'icon-mpr',
      iconLabel: 'MPR',
      label: 'MPR / Slab Controls',
      component: wrap(MPRSlabControlsPanel, "mprSlabPanel"),
    },
    {
      name: 'hotkeyHelpPanel',
      iconName: 'info',
      iconLabel: 'Keys',
      label: 'Tastenkuerzel',
      component: wrap(HotkeyHelpPanel, "hotkeyHelpPanel"),
    },
  ];
}

export default getPanelModule;
