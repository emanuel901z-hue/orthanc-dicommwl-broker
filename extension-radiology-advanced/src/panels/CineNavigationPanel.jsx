// CineNavigationPanel - Cine/4D-Navigation fuer dynamische Serien
//
// Bietet Steuerelemente fuer 4D/dynamische Serien:
//  - Play/Pause Cine-Wiedergabe
//  - Frame-Navigation (Slider, vor/zurueck, erster/letzter)
//  - Geschwindigkeitsregelung (FPS)
//  - Loop-Modus (Einmal, Endlos, Ping-Pong)
//
// Ergaenzt das TIC-Panel um interaktive Steuerelemente.
// Nutzt den cineService von OHIF und die Cornerstone3D Stack-API.

import React, { useState, useEffect, useCallback } from 'react';

function CineNavigationPanel({ servicesManager, commandsManager }) {
  const { cineService, cornerstoneViewportService, viewportGridService, displaySetService } =
    servicesManager?.services || {};

  const [isPlaying, setIsPlaying] = useState(false);
  const [currentFrame, setCurrentFrame] = useState(0);
  const [totalFrames, setTotalFrames] = useState(0);
  const [fps, setFps] = useState(10);
  const [loopMode, setLoopMode] = useState('continuous'); // 'continuous' | 'once' | 'pingpong'
  const [activeViewportId, setActiveViewportId] = useState(null);
  const [statusMsg, setStatusMsg] = useState('');

  // Aktiven Viewport und Frame-Status verfolgen
  useEffect(() => {
    if (!viewportGridService || !cineService) return;

    const updateState = () => {
      const state = viewportGridService.getState();
      const vpId = state?.activeViewportId;
      setActiveViewportId(vpId);

      if (vpId && cineService) {
        const cineState = cineService.getState?.();
        const vpCine = cineState?.viewports?.[vpId];
        if (vpCine) {
          setIsPlaying(vpCine.isPlaying || false);
          setFps(vpCine.frameRate || 10);
        }
      }

      // Frame-Anzahl aus dem Cornerstone-Viewport ermitteln
      if (vpId && cornerstoneViewportService) {
        const csViewport = cornerstoneViewportService.getCornerstoneViewport(vpId);
        if (csViewport) {
          const imageData = csViewport.getImageData?.();
          // Fuer Stack-Viewports: Anzahl der Slices
          const numImages = csViewport.getNumberOfSlices?.() ||
                           imageData?.imageIds?.length ||
                           0;
          setTotalFrames(numImages);

          const currentIndex = csViewport.getCurrentImageIdIndex?.() ||
                              csViewport.getSliceIndex?.() ||
                              0;
          setCurrentFrame(currentIndex);
        }
      }
    };

    updateState();

    const subs = [];
    subs.push(viewportGridService.subscribe?.(
      viewportGridService.EVENTS?.ACTIVE_VIEWPORT_ID_CHANGED, updateState
    ));
    subs.push(cineService?.subscribe?.(
      cineService.EVENTS?.CINE_STATE_CHANGED, updateState
    ));

    return () => subs.forEach(s => s?.unsubscribe?.());
  }, [viewportGridService, cineService, cornerstoneViewportService]);

  // Play/Pause umschalten
  // Verwendet cineService.getState() statt isPlaying aus dem Closure,
  // um immer den aktuellen State zu lesen (vermeidet stale closures).
  const togglePlay = useCallback(() => {
    if (!cineService || !activeViewportId) {
      setStatusMsg('CineService nicht verfuegbar');
      return;
    }

    // Aktuellen State aus dem Service lesen (statt aus React-State-Closure).
    const cineData = cineService.getCine?.(activeViewportId);
    const currentState = cineData ? !!cineData.isPlaying : false;

    try {
      cineService.setCine({ viewportId: activeViewportId, isPlaying: !currentState });
      setIsPlaying(!currentState);
      setStatusMsg(currentState ? 'Pause' : 'Wiedergabe');
    } catch (err) {
      // Fallback ueber toggleCine-Command (keine Parameter)
      if (commandsManager) {
        try {
          commandsManager.runCommand('toggleCine');
          setIsPlaying(!currentState);
          setStatusMsg(currentState ? 'Pause' : 'Wiedergabe');
        } catch (cmdErr) {
          console.warn('[CineNav] toggleCine fehlgeschlagen:', cmdErr.message);
        }
      }
      if (!commandsManager) {
        setStatusMsg('Cine-Fehler: ' + err.message);
      }
    }
  }, [cineService, activeViewportId, commandsManager]);

  // Zu Frame springen
  const goToFrame = useCallback((frameIndex) => {
    if (!activeViewportId) return;

    try {
      // Primärer Weg: cineService fuer Frame-Wechsel
      if (cineService) {
        cineService.setCine({ viewportId: activeViewportId, frameIndex });
      }
      // jumpToImage als Fallback nur wenn cineService nicht verfuegbar
      if (!cineService && commandsManager) {
        commandsManager.runCommand('jumpToImage', { viewportId: activeViewportId, imageIndex: frameIndex });
      }
      setCurrentFrame(frameIndex);
    } catch (err) {
      setStatusMsg('Frame-Fehler: ' + err.message);
    }
  }, [cineService, activeViewportId, commandsManager]);

  // FPS aendern
  const changeFps = useCallback((newFps) => {
    setFps(newFps);
    if (cineService && activeViewportId) {
      cineService.setCine({ viewportId: activeViewportId, frameRate: newFps });
    }
  }, [cineService, activeViewportId]);

  // Loop-Modus aendern und an cineService weitergeben
  const changeLoopMode = useCallback((mode) => {
    setLoopMode(mode);
    if (cineService && activeViewportId) {
      try {
        cineService.setCine({ viewportId: activeViewportId, loop: mode });
      } catch (e) {
        // loop-Parameter wird ggf. nicht unterstuetzt - nicht kritisch
      }
    }
  }, [cineService, activeViewportId]);

  // Naechster / vorheriger Frame
  const nextFrame = useCallback(() => {
    const next = Math.min(currentFrame + 1, totalFrames - 1);
    goToFrame(next);
  }, [currentFrame, totalFrames, goToFrame]);

  const prevFrame = useCallback(() => {
    const prev = Math.max(currentFrame - 1, 0);
    goToFrame(prev);
  }, [currentFrame, goToFrame]);

  const firstFrame = useCallback(() => goToFrame(0), [goToFrame]);
  const lastFrame = useCallback(() => goToFrame(totalFrames - 1), [totalFrames, goToFrame]);

  const btnStyle = {
    padding: '8px 12px', border: '1px solid #444', borderRadius: '4px',
    background: '#1a2a4a', color: '#e0e0e0', cursor: 'pointer', fontSize: '14px',
  };
  const playBtnStyle = {
    ...btnStyle, background: isPlaying ? '#c73a2a' : '#2a6cc7', color: '#fff',
    fontWeight: 'bold', fontSize: '16px', padding: '10px 20px',
  };

  return React.createElement('div', {
    style: { padding: '8px', height: '100%', overflow: 'auto', background: '#0d1117' },
    'data-cy': 'cine-nav-panel',
  },
    // Header
    React.createElement('h3', {
      style: { color: '#e0e0e0', fontSize: '14px', margin: '0 0 8px 0', borderBottom: '1px solid #333', paddingBottom: '4px' },
    }, 'Cine / 4D-Navigation'),

    // Frame-Anzeige
    React.createElement('div', {
      style: { background: '#161b22', padding: '10px', borderRadius: '4px', marginBottom: '12px', textAlign: 'center' },
    },
      React.createElement('div', { style: { fontSize: '24px', fontWeight: 'bold', color: '#4ec9b0' } },
        (currentFrame + 1) + ' / ' + totalFrames
      ),
      React.createElement('div', { style: { fontSize: '10px', color: '#666', marginTop: '2px' } },
        'Viewport: ' + (activeViewportId || '(keiner)')
      ),
    ),

    // Frame-Slider
    totalFrames > 0 && React.createElement('div', { style: { marginBottom: '12px' } },
      React.createElement('input', {
        type: 'range', min: 0, max: totalFrames - 1, value: currentFrame,
        onChange: e => goToFrame(parseInt(e.target.value)),
        style: { width: '100%', cursor: 'pointer' },
        'data-cy': 'cine-slider',
      })
    ),

    // Navigations-Buttons
    React.createElement('div', {
      style: { display: 'flex', gap: '4px', justifyContent: 'center', marginBottom: '12px' },
    },
      React.createElement('button', { style: btnStyle, onClick: firstFrame, title: 'Erster Frame' }, '\u23EE'),
      React.createElement('button', { style: btnStyle, onClick: prevFrame, title: 'Vorheriger' }, '\u23F4'),
      React.createElement('button', { style: playBtnStyle, onClick: togglePlay, title: isPlaying ? 'Pause' : 'Play' },
        isPlaying ? '\u23F8' : '\u25B6'
      ),
      React.createElement('button', { style: btnStyle, onClick: nextFrame, title: 'Naechster' }, '\u23F5'),
      React.createElement('button', { style: btnStyle, onClick: lastFrame, title: 'Letzter Frame' }, '\u23ED'),
    ),

    // FPS-Regler
    React.createElement('div', { style: { marginBottom: '12px' } },
      React.createElement('label', { style: { display: 'block', fontSize: '11px', color: '#999', marginBottom: '4px' } },
        'Geschwindigkeit: ' + fps + ' fps'
      ),
      React.createElement('input', {
        type: 'range', min: 1, max: 30, value: fps,
        onChange: e => changeFps(parseInt(e.target.value)),
        style: { width: '100%', cursor: 'pointer' },
        'data-cy': 'cine-fps-slider',
      }),
    ),

    // Loop-Modus
    React.createElement('div', { style: { marginBottom: '12px' } },
      React.createElement('label', { style: { display: 'block', fontSize: '11px', color: '#999', marginBottom: '4px' } }, 'Wiederholung:'),
      React.createElement('div', { style: { display: 'flex', gap: '4px' } },
        [
          { value: 'continuous', label: 'Endlos' },
          { value: 'once', label: 'Einmal' },
          { value: 'pingpong', label: 'Ping-Pong' },
        ].map(mode =>
          React.createElement('button', {
            key: mode.value,
            style: {
              flex: 1, padding: '6px', border: 'none', borderRadius: '3px',
              background: loopMode === mode.value ? '#2a6cc7' : '#333',
              color: loopMode === mode.value ? '#fff' : '#999',
              cursor: 'pointer', fontSize: '11px',
            },
            onClick: () => changeLoopMode(mode.value),
          }, mode.label)
        )
      )
    ),

    // Status
    statusMsg && React.createElement('div', {
      style: { color: '#4ec9b0', fontSize: '11px', padding: '4px', background: '#0a1a1a', borderRadius: '3px' },
    }, statusMsg),

    // Hinweis
    React.createElement('div', {
      style: { color: '#666', fontSize: '10px', marginTop: '12px', padding: '6px', background: '#161b22', borderRadius: '3px' },
    }, 'Steuert die Cine-Wiedergabe des aktiven Viewports. Fuer 4D/dynamische Serien (Perfusion, dynamisches MRT) koennen Sie durch alle Zeitpunkte scrollen oder automatisch abspielen lassen.'),
  );
}

export default CineNavigationPanel;
