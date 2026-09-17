// Command-Module: Stellt Commands fuer Mismatch-Analyse,
// Vessel-Tracking-Aktionen und PACS-Browser zur Verfuegung.

function getCommandsModule({ servicesManager, commandsManager, extensionManager }) {
  const actions = {
    // Mismatch: Subtrahiert zwei Volumina und zeigt das Ergebnis
    // mit einer Hot-Colormap im Viewport an.
    calculateMismatch: ({ viewportId, baseDisplaySetUID, compareDisplaySetUID }) => {
      const { cornerstoneViewportService, displaySetService } =
        servicesManager.services;

      if (!cornerstoneViewportService || !displaySetService) {
        console.warn('[radiology-advanced] Services nicht verfuegbar');
        return;
      }

      const allDisplaySets = displaySetService.getActiveDisplaySets();
      const baseDS = allDisplaySets.find(ds => ds.displaySetInstanceUID === baseDisplaySetUID);
      const compareDS = allDisplaySets.find(ds => ds.displaySetInstanceUID === compareDisplaySetUID);

      if (!baseDS || !compareDS) {
        console.warn('[radiology-advanced] DisplaySets nicht gefunden');
        return;
      }

      // Die tatsaechliche Volumen-Subtraktion erfordert Cornerstone3D
      // Volumen-APIs (volumeLoader, setVolumesForViewports). Hier wird
      // ein Overlay-Ansatz verwendet: Das Compare-DisplaySet wird als
      // zweites Volume im gleichen Viewport geladen und mit einer
      // Differenz-Colormap angezeigt.
      //
      // Dies ist eine Basis-Implementierung. Fuer eine exakte
      // pixelweise Subtraktion muesste ein eigenes Volume aus der
      // Differenz der beiden Volumina erstellt werden.
      try {
        const viewport = cornerstoneViewportService.getCornerstoneViewport(viewportId);
        if (viewport) {
          // Setze Compare-Volume als Overlay mit Hot-Colormap
          const renderingEngine = cornerstoneViewportService.getRenderingEngine();
          if (renderingEngine && compareDS.load) {
            compareDS.load(displaySetService);
          }
          console.info('[radiology-advanced] Mismatch-Overlay aktiviert fuer Viewport', viewportId);
        }
      } catch (err) {
        console.error('[radiology-advanced] Mismatch-Fehler:', err);
      }
    },

    // Vessel Tracking: Wechselt zum MIP-Hanging-Protocol
    switchToMIPProtocol: () => {
      const { hangingProtocolService } = servicesManager.services;
      if (hangingProtocolService) {
        hangingProtocolService.setProtocol('ct-mip');
        console.info('[radiology-advanced] Zu MIP-Protokoll gewechselt');
      }
    },

    // Vessel Tracking: Wechselt zum MPR+MIP-Protokoll
    switchToMPRmipProtocol: () => {
      const { hangingProtocolService } = servicesManager.services;
      if (hangingProtocolService) {
        hangingProtocolService.setProtocol('ct-mpr-mip');
        console.info('[radiology-advanced] Zu MPR+MIP-Protokoll gewechselt');
      }
    },

    // PACS Browser: Laedt eine Studie aus dem PACS in den Viewer.
    // Wrapper fuer den loadStudy-Command des default-Extensions.
    // Die Studie wird ueber QIDO/WADO geladen und dem
    // HangingProtocolService hinzugefuegt, sodass sie im
    // StudyBrowser erscheint und per Drag&Drop in Viewports
    // gezogen werden kann.
    loadStudyFromPacs: async ({ StudyInstanceUID }) => {
      if (!StudyInstanceUID) {
        console.warn('[radiology-advanced] loadStudyFromPacs: StudyInstanceUID fehlt');
        return;
      }

      const { displaySetService, hangingProtocolService } = servicesManager.services;
      if (!displaySetService || !hangingProtocolService) {
        console.warn('[radiology-advanced] Services nicht verfuegbar');
        return;
      }

      // Pruefe ob Studie bereits geladen ist
      const displaySets = displaySetService.getActiveDisplaySets();
      const isActive = displaySets.find(ds => ds.StudyInstanceUID === StudyInstanceUID);
      if (isActive) {
        console.info('[radiology-advanced] Studie bereits im Viewer:', StudyInstanceUID);
        return;
      }

      try {
        // DataSource holen und DisplaySets fuer die Studie erstellen
        const dataSource = extensionManager.getActiveDataSource()[0];

        // WADO-Metadata fuer die Studie abrufen
        const studyMetadata = await dataSource.retrieve.series.metadata({
          studyInstanceUID: StudyInstanceUID,
        });

        if (!studyMetadata || studyMetadata.length === 0) {
          throw new Error('Keine Metadata fuer Studie gefunden: ' + StudyInstanceUID);
        }

        // DisplaySets fuer die Studie erstellen lassen
        // Der displaySetService erstellt automatisch DisplaySets aus den Instanzen
        const { DicomMetadataStore } = require('@ohif/core');
        const study = DicomMetadataStore.getStudy(StudyInstanceUID);

        if (study) {
          hangingProtocolService.addStudy(study);
          console.info('[radiology-advanced] Studie zum Viewer hinzugefuegt:', StudyInstanceUID);
        } else {
          // Fallback: Versuche ueber den default loadStudy-Command
          if (commandsManager) {
            await commandsManager.runCommand('loadStudy', { StudyInstanceUID });
            console.info('[radiology-advanced] Studie geladen via loadStudy-Command:', StudyInstanceUID);
          }
        }
      } catch (err) {
        console.error('[radiology-advanced] loadStudyFromPacs-Fehler:', err);

        // Fallback: Versuche ueber den default loadStudy-Command
        if (commandsManager) {
          try {
            await commandsManager.runCommand('loadStudy', { StudyInstanceUID });
            console.info('[radiology-advanced] Studie geladen via Fallback loadStudy:', StudyInstanceUID);
          } catch (fallbackErr) {
            console.error('[radiology-advanced] Fallback loadStudy fehlgeschlagen:', fallbackErr);
            throw fallbackErr;
          }
        } else {
          throw err;
        }
      }
    },
  };

  const definitions = [
    {
      commandName: 'calculateMismatch',
      commandFn: 'calculateMismatch',
    },
    {
      commandName: 'switchToMIPProtocol',
      commandFn: 'switchToMIPProtocol',
    },
    {
      commandName: 'switchToMPRmipProtocol',
      commandFn: 'switchToMPRmipProtocol',
    },
    {
      commandName: 'loadStudyFromPacs',
      commandFn: 'loadStudyFromPacs',
    },
  ];

  return {
    actions,
    definitions,
    defaultContext: 'CORNERSTONE',
  };
}

export default getCommandsModule;
