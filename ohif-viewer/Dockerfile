# syntax=docker/dockerfile:1
#
# Multi-Stage-Build des OHIF v3 Viewers fuer Carestream PACS (DICOMweb).
# Stage 1: OHIF aus dem Quelltext (Tag v3.12.5) bauen.
# Stage 2: Build-Artefakte mit nginx ausliefern.
#
# Die OHIF-App-Konfiguration (default.js) wird aus dem Build-Context
# (ohif-viewer/default.js) in platform/app/public/config/ kopiert und
# damit in den Build eingebaut.
#
# Build-Context ist das Projekt-Root-Verzeichnis (.), damit sowohl
# ohif-viewer/ als auch extension-radiology-advanced/ zugreifbar sind.

########################################
# Stage 1: Build
########################################
FROM node:20-bookworm-slim AS builder

# Build-Abhaengigkeiten fuer native Module (z.B. canvas, libpng).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        ca-certificates \
        python3 \
        make \
        g++ \
        libpng-dev \
        libjpeg-dev \
        libcairo2-dev \
        libpango1.0-dev \
        libgif-dev \
        librsvg2-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# OHIF v3 stabile Version v3.12.5 auschecken.
# Pinning auf einen Tag gewaehrleistet reproduzierbare Builds.
RUN git clone --depth 1 --branch v3.12.5 https://github.com/OHIF/Viewers.git .

# Bun installieren (wird vom OHIF v3.12.5 Build-Script benoetigt).
RUN npm install -g bun

# Eigene App-Konfiguration: Die modularen Protokoll-Dateien werden
# von build-config.js zu default.js assembliert. Danach wird die
# generierte default.js in den OHIF-Build kopiert.
# Module: protocols/*.js + static-config.js -> default.js
COPY ohif-viewer/build-config.js ohif-viewer/static-config.js /tmp/ohif-config/
COPY ohif-viewer/protocols /tmp/ohif-config/protocols/
RUN node /tmp/ohif-config/build-config.js \
    && cp /tmp/ohif-config/default.js platform/app/public/config/default.js \
    && rm -rf /tmp/ohif-config

# Eigene Extension extension-radiology-advanced in den OHIF-Quelltext
# kopieren. Die Extension wird ueber das yarn-workspace (extensions/*)
# und pluginConfig.json in den Build eingebunden. Sie stellt:
#  - sameAs Custom Attribute fuer PET/CT-Fusion (Hanging Protocol)
#  - TIC Panel (Time-Intensity Curve)
#  - Mismatch Panel (Vergleich zweier Bildserien)
#  - Vessel Tracking Panel (MIP-Anleitung, Mess-Tools)
COPY extension-radiology-advanced extensions/extension-radiology-advanced

# Hanging Protocols in die Extension kopieren und von CommonJS
# (module.exports) zu ES-Modulen (export default) konvertieren.
# OHIF v3 registriert Protokolle NICHT aus window.config.hangingProtocols,
# sondern ueber getHangingProtocolModule der Extensions. Die Default-
# Extension registriert nur 6 Basis-Protokolle. Unsere 80 custom Protokolle
# aus ohif-viewer/protocols/*.js werden in die Extension kopiert und
# als ES-Module verfuegbar gemacht.
COPY ohif-viewer/protocols /tmp/protocols
RUN mkdir -p extensions/extension-radiology-advanced/src/hangingProtocols && \
    for f in /tmp/protocols/*.js; do \
      base=$(basename "$f"); \
      sed 's/module\.exports =/export default/' "$f" > \
        "extensions/extension-radiology-advanced/src/hangingProtocols/$base"; \
    done && \
    rm -rf /tmp/protocols && \
    echo "Protocols copied and converted to ES modules: $(ls extensions/extension-radiology-advanced/src/hangingProtocols/ | wc -l) files"

# Root package.json patchen: Extension als Dependency registrieren,
# damit yarn workspace sie als Package linkt und der webpack-build
# sie findet. Die workspaces-Regel "extensions/*" erfasst das
# Verzeichnis, aber yarn install muss die Dependency kennen.
RUN node -e "\
  const fs = require('fs'); \
  const p = 'package.json'; \
  const c = JSON.parse(fs.readFileSync(p, 'utf8')); \
  if (!c.dependencies) c.dependencies = {}; \
  if (!c.dependencies['@ohif/extension-radiology-advanced']) { \
    c.dependencies['@ohif/extension-radiology-advanced'] = '1.0.0'; \
    console.log('package.json: @ohif/extension-radiology-advanced als Dependency hinzugefuegt'); \
  } \
  fs.writeFileSync(p, JSON.stringify(c, null, 2)); \
"

# pluginConfig.json patchen: Extension registrieren, damit sie vom
# Build-Process (pluginImports.js) geladen wird. Mit default: true
# wird sie automatisch in allen Modes verfuegbar.
RUN node -e "\
  const fs = require('fs'); \
  const p = 'platform/app/pluginConfig.json'; \
  const c = JSON.parse(fs.readFileSync(p, 'utf8')); \
  if (!c.extensions.find(e => e.packageName === '@ohif/extension-radiology-advanced')) { \
    c.extensions.push({ \
      packageName: '@ohif/extension-radiology-advanced', \
      default: true, \
      version: '1.0.0' \
    }); \
  } \
  /* SR, PDF, SEG, RT, PMAP, Video, dynamic-volume auf default:true setzen, \
     damit deren sopClassHandler immer geladen werden und DisplaySets nicht \
     als "unsupported" markiert werden. */ \
  const enableExts = [ \
    '@ohif/extension-cornerstone-dicom-sr', \
    '@ohif/extension-dicom-pdf', \
    '@ohif/extension-cornerstone-dicom-seg', \
    '@ohif/extension-cornerstone-dicom-rt', \
    '@ohif/extension-cornerstone-dicom-pmap', \
    '@ohif/extension-dicom-video', \
    '@ohif/extension-cornerstone-dynamic-volume', \
  ]; \
  let enabled = 0; \
  for (const ext of c.extensions) { \
    if (enableExts.includes(ext.packageName) && ext.default !== true) { \
      ext.default = true; \
      enabled++; \
    } \
  } \
  fs.writeFileSync(p, JSON.stringify(c, null, 2)); \
  console.log('pluginConfig.json: extension-radiology-advanced hinzugefuegt, ' + enabled + ' Extensions auf default:true gesetzt'); \
"

# mode-basic und mode-longitudinal patchen:
# 1. Extension zur extensions-Liste des Modes hinzufuegen.
# 2. Panel-Module der Extension zur rightPanels-Liste des Layouts hinzufuegen,
#    damit sie als Tabs in der rechten Sidebar erscheinen.
# 3. rightPanelClosed auf false setzen, damit die Sidebar geoeffnet ist.
RUN node -e "\
  const fs = require('fs'); \
  const panelNames = [ \
    'dicomTagBrowserPanel', \
    'roiStatsPanel', \
    'measurementExportPanel', \
    'mprSlabPanel', \
    'wlPresetsPanel', \
    'studyComparePanel', \
    'hotkeyHelpPanel', \
  ]; \
  const panelEntries = panelNames.map(n => \
    \"'@ohif/extension-radiology-advanced.panelModule.\" + n + \"'\" \
  ).join(', '); \
  \
  /* --- mode-basic patchen --- */ \
  const basicPath = 'modes/basic/src/index.tsx'; \
  if (fs.existsSync(basicPath)) { \
    let src = fs.readFileSync(basicPath, 'utf8'); \
    if (!src.includes('@ohif/extension-radiology-advanced')) { \
      /* Extension zur extensionDependencies hinzufuegen */ \
      src = src.replace( \
        /(['\"]@ohif\/extension-default['\"]: ?['\"][^'\"]+['\"])/, \
        \"\\\$1,\\n  '@ohif/extension-radiology-advanced': '1.0.0'\" \
      ); \
      /* radAdv-Konstante nach der cornerstone-Konstante einfuegen */ \
      src = src.replace( \
        /export const cornerstone = \{/, \
        \"export const radAdv = {\\n\" + \
        panelNames.map(n => \"  \" + n + \": '@ohif/extension-radiology-advanced.panelModule.\" + n + \"',\").join('\\n') + \"\\n};\\n\\nexport const cornerstone = {\" \
      ); \
      /* rightPanels erweitern und rightPanelClosed auf false */ \
      src = src.replace( \
        /rightPanels:\s*\[cornerstone\.segmentation,\s*cornerstone\.measurements\]/, \
        'rightPanels: [cornerstone.segmentation, cornerstone.measurements, ' + panelEntries + ']' \
      ); \
      src = src.replace( \
        /rightPanelClosed:\s*true/, \
        'rightPanelClosed: false' \
      ); \
      /* hangingProtocol auf undefined setzen fuer auto-matching */ \
      src = src.replace( \
        /hangingProtocol:\s*['\"]default['\"]/, \
        'hangingProtocol: undefined' \
      ); \
      fs.writeFileSync(basicPath, src); \
      console.log('modes/basic: extension-radiology-advanced + panels hinzugefuegt'); \
    } else { \
      console.log('modes/basic: bereits gepatcht'); \
    } \
  } \
  \
  /* --- mode-longitudinal patchen --- */ \
  const longPath = 'modes/longitudinal/src/index.ts'; \
  if (fs.existsSync(longPath)) { \
    let src = fs.readFileSync(longPath, 'utf8'); \
    if (!src.includes('@ohif/extension-radiology-advanced')) { \
      /* Extension zur extensionDependencies hinzufuegen */ \
      src = src.replace( \
        /(['\"]@ohif\/extension-measurement-tracking['\"]: ?['\"][^'\"]+['\"])/, \
        \"\\\$1,\\n  '@ohif/extension-radiology-advanced': '1.0.0'\" \
      ); \
      /* rightPanels erweitern */ \
      src = src.replace( \
        /rightPanels:\s*\[cornerstone\.segmentation,\s*tracked\.measurements\]/, \
        'rightPanels: [cornerstone.segmentation, tracked.measurements, ' + panelEntries + ']' \
      ); \
      fs.writeFileSync(longPath, src); \
      console.log('modes/longitudinal: extension-radiology-advanced + panels hinzugefuegt'); \
    } else { \
      console.log('modes/longitudinal: bereits gepatcht'); \
    } \
  } \
"

# SidePanel-Patch: Bei 14 Tabs (2 OHIF + 12 Extension) berechnet OHIF
# 5 Spalten, was 3 Reihen erfordert. Der Original-Header-Container hat
# eine feste Hoehe von h-[40px], was nur eine Reihe aufnehmen kann.
# Weitere Reihen werden abgeschnitten und sind unsichtbar.
# Fix: h-[40px] -> min-h-[40px], damit der Container mit den Tabs wächst.
# flex-wrap bleibt erhalten (kein overflow-x-auto), damit Tabs sauber
# in mehrere Reihen umbrechen.
RUN sed -i 's/h-\[40px\] flex-shrink-0/min-h-[40px] flex-shrink-0/' \
      platform/ui-next/src/components/SidePanel/SidePanel.tsx

# StudyBrowser-Patch: StudyBrowser.tsx destrukturiert nur date, description,
# numInstances, modalities, displaySets aus den Studien-Objekten. Patientendaten
# (patientName, mrn, accession, patientBirthDate) werden nicht an StudyItem
# durchgereicht. Patch fuegt die Felder zur Destrukturierung und als Props hinzu.
# StudyItem-Patch: Zeigt Patientendaten (Name, MRN, Accession, Geburtsdatum)
# im Studien-Browser links an. Formatierung: Datum DD.MM.YYYY, Patientenname
# "Nachname, Vorname". Hoehe von h-[40px] auf min-h-[60px] fuer 3 Zeilen.
COPY ohif-viewer/patch-studyitem.js /tmp/patch-studyitem.js
RUN node /tmp/patch-studyitem.js && rm /tmp/patch-studyitem.js

# Quick check: verify mode patches were applied
COPY ohif-viewer/check-patches.js /tmp/check-patches.js
RUN node /tmp/check-patches.js && rm /tmp/check-patches.js

# Onboarding-Tour (Shepherd) deaktivieren: Die Standard-Tour versucht
# .viewport-element zu finden und legt einen modalen Overlay ueber die
# gesamte UI, wenn das Element nicht (rechtzeitig) gefunden wird. Das
# blockiert alle Klicks (Panel-Tabs, Buttons, etc.). Die Tour ist als
# Default-Customization in onboardingCustomization.ts registriert und
# kann nicht ueber app-config ueberschrieben werden. Patch ersetzt die
# gesamte Datei durch ein leeres ohif.tours Array.
RUN echo "export default { 'ohif.tours': [] };" > \
    extensions/default/src/customizations/onboardingCustomization.ts && \
    echo "onboardingCustomization.ts ersetzt: Tours deaktiviert"

# SR BulkData-Patch: Der Carestream PACS liefert einige SR-Werte als
# Bulk-Data-Referenz ({BulkDataURI, retrieveBulkData}) statt als inline
# String. OHIFs formatContentItem.ts gibt dieses Objekt zurueck, und React
# stuerzt mit Error #31 ab (Objekte koennen nicht als React-Child gerendert
# werden). Patch wrapped alle Formatter mit _safeValue(), das Objekte in
# Platzhalter-Strings umwandelt und asynchrones Nachladen anstoesst.
COPY ohif-viewer/patch-sr-bulkdata.js /tmp/patch-sr-bulkdata.js
RUN node /tmp/patch-sr-bulkdata.js && rm /tmp/patch-sr-bulkdata.js

# StudyBrowser-Patch: Studien, die ueber den PACS Browser geladen wurden,
# erscheinen normalerweise nicht im StudyBrowser links, da dieser seine
# Liste aus QIDO-Suchen nach Patienten-MRN aufbaut. Der Patch fuegt
# DisplaySets, deren StudyInstanceUID nicht in studyDisplayList ist, als
# zusaetzliche Studien hinzu, damit sie im "Alle" und "Aktuell" Tab des
# StudyBrowsers erscheinen (mit Beschreibung, Datum, Modality,
# Patientendaten). Patientendaten werden aus DicomMetadataStore geholt,
# da DisplaySets diese nicht direkt enthalten.
# Ausgelagert in ein Node-Script fuer bessere Wartbarkeit und Fehlerbehandlung.
COPY ohif-viewer/patch-studybrowser-tabs.js /tmp/patch-studybrowser-tabs.js
RUN node /tmp/patch-studybrowser-tabs.js && rm /tmp/patch-studybrowser-tabs.js

# Webpack-Patch: __filename und __dirname definieren, damit ONNX Runtime
# Web (ort.webgpu.min.js) keinen ReferenceError wirft. Im Web-Target sind
# diese Node.js-Variablen nicht definiert. DefinePlugin ersetzt sie durch
# leere Strings.
RUN sed -i "s/const defineValues = {/const defineValues = {\n  '__filename': JSON.stringify(''),\n  '__dirname': JSON.stringify(''),/" .webpack/webpack.base.js

# Unsupported-DisplaySet-Patch: Verhindert Absturz beim Klick auf Thumbnails
# von unsupported DisplaySets (SR, PDF, ungewoehnliche SC-Bilder).
# canAddDisplaySetToViewport und addDisplaySetAsLayer pruefen auf das
# `unsupported` Flag und verhindern den Aufruf von getViewportsRequireUpdate,
# das sonst "Unsupported displaySet" wirft.
COPY ohif-viewer/patch-unsupported-displayset.js /tmp/patch-unsupported-displayset.js
RUN node /tmp/patch-unsupported-displayset.js && rm /tmp/patch-unsupported-displayset.js

# Dynamic-Volume-Patch: Verhindert Absturz bei unvollstaendigen Metadaten
# (z.B. SC-Bilder mit fehlender PixelSpacing von Carestream/AVIEW).
# getDynamicVolumeInfo wird in try-catch gewrappt und faellt auf
# nicht-dynamisch zurueck, wenn splitImageIdsBy4DTags fehlschlaegt.
COPY ohif-viewer/patch-dynamic-volume.js /tmp/patch-dynamic-volume.js
RUN node /tmp/patch-dynamic-volume.js && rm /tmp/patch-dynamic-volume.js

# Encapsulated-PDF-Frames-Patch: Verhindert "Error: request failed" beim
# Laden von AVIEW/Polaris CAD Studien mit Encapsulated PDF (SOP Class 104.1)
# und Modality "CT". Der dicom-pdf Handler verwendet ab jetzt direkt
# `instance.EncapsulatedDocument.BulkDataURI` als renderedUrl, da Orthanc
# weder `/rendered` fuer PDF unterstuetzt noch `retrieveBulkData` an die
# BulkDataURI anhaengt. `unsupported:true` entfaellt, damit der dicom-pdf
# Viewport das DisplaySet oeffnen kann. Zusaetzlich wird der dicomweb-client
# gepatcht, um 400 bei frames/1 als "no data" zu behandeln (Fallback fuer
# Thumbnail-Prefetcher/HangingProtocol).
COPY ohif-viewer/patch-encapsulated-pdf-frames.js /tmp/patch-encapsulated-pdf-frames.js
RUN node /tmp/patch-encapsulated-pdf-frames.js && rm /tmp/patch-encapsulated-pdf-frames.js

# SR-SOP-Class-Patch: Erweitert den dicom-sr Handler um zusaetzliche
# SR-Typen (XRayRadiationDoseSR 88.67, MammographyCADSR 88.50, etc.),
# die sonst als "unsupported" markiert werden.
COPY ohif-viewer/patch-sr-sopclass.js /tmp/patch-sr-sopclass.js
RUN node /tmp/patch-sr-sopclass.js && rm /tmp/patch-sr-sopclass.js

# VTK.js Shader-Null-Patch: Verhindert TypeError "Cannot read properties of null
# (reading 'isAttributeUsed')" in setMapperShaderParameters beim Rendern von
# SEG-Daten oder bei GPU-Memory-Erschoepfung (WebGL Context Loss).
# Bekannte Issues: OHIF/Viewers#6010, #2318, Kitware/vtk-js#1814
# Patch muss NACH yarn install laufen (node_modules muss existieren).
COPY ohif-viewer/patch-vtk-shader-null.js /tmp/patch-vtk-shader-null.js

# Abhaengigkeiten installieren und Produktions-Build erstellen.
# Yarn mit --network-concurrency 1 erhoht die Stabilitaet bei
# eingeschraenkten Netzwerken.
# --frozen-lockfile wird nicht verwendet, da die eigene Extension
# nicht im Original-Lockfile von OHIF v3.12.5 enthalten ist.
# v3.48.18: PUBLIC_URL=/ohif/ damit webpack Asset-Pfade als /ohif/app.bundle.js
# generiert (statt /app.bundle.js). Der Viewer wird unter /ohif/ proxied.
ENV PUBLIC_URL=/ohif/
RUN yarn config set network-concurrency 1 \
    && yarn install --no-progress \
    && node /tmp/patch-vtk-shader-null.js \
    && yarn build \
    && rm -f /tmp/patch-vtk-shader-null.js

########################################
# Stage 2: Runtime (nginx)
########################################
FROM nginx:1.27-alpine AS runtime

# Build-Artefakte in das nginx-DocumentRoot kopieren.
RUN mkdir -p /usr/share/nginx/html
COPY --from=builder /app/platform/app/dist/ /usr/share/nginx/html/

# Service Worker deaktivieren: Das init-service-worker.js ruft
# navigator.serviceWorker.getRegistrations() ohne Existenzpruefung auf.
# Im HTTP-Kontext (ohne HTTPS) ist navigator.serviceWorker undefined,
# was zu einem TypeError fuehrt. Fuer den RIS-Einsatz ist der Service
# Worker (Offline-Caching) nicht relevant.
RUN echo "// Service Worker deaktiviert (HTTP-Kontext)" > /usr/share/nginx/html/init-service-worker.js

# Custom CSS: Thin scrollbar fuer die SidePanel-Tab-Grid.
COPY ohif-viewer/custom-styles.css /usr/share/nginx/html/custom-styles.css
RUN sed -i 's|</head>|<link rel="stylesheet" href="/custom-styles.css"></head>|' /usr/share/nginx/html/index.html

# Clipboard-Polyfill: Die Clipboard-API (navigator.clipboard) ist nur in
# sicheren Kontexten (HTTPS/localhost) verfuegbar. Im RIS-Einsatz wird OHIF
# ueber HTTP ausgeliefert, sodass navigator.clipboard undefined ist und
# Klicks auf "Kopieren"-Buttons (z.B. Study-URL teilen, Tag-Wert kopieren)
# mit "Cannot read properties of undefined (reading 'writeText')" abstuerzen.
# Der Polyfill erstellt ein Fallback-Objekt mit writeText ueber
# document.execCommand('copy') und eine unsichtbare Textarea.
RUN sed -i 's|</head>|<script>\
if (!navigator.clipboard) {\
  navigator.clipboard = {\
    writeText: function(text) {\
      return new Promise(function(resolve, reject) {\
        var ta = document.createElement("textarea");\
        ta.value = text;\
        ta.style.position = "fixed";\
        ta.style.opacity = "0";\
        document.body.appendChild(ta);\
        ta.select();\
        try { document.execCommand("copy"); resolve(); }\
        catch (e) { reject(e); }\
        document.body.removeChild(ta);\
      });\
    },\
    readText: function() { return Promise.reject(new Error("Clipboard API not available in HTTP context")); }\
  };\
}\
</script></head>|' /usr/share/nginx/html/index.html

# Encapsulated-PDF-Frames-Patch (post-build): Der dicomweb-client (gebundelt
# im 2108.bundle) wirft bei 400 Bad Request einen Error "request failed".
# Bei Encapsulated PDF (SOP Class 104.1) mit Modality "CT" von AVIEW/Polaris
# CAD gibt Orthanc 400 bei frames/1-Requests zurueck (keine Pixel-Daten).
# Post-build sed-Patch fuegt eine 400-Ausnahme fuer /frames/-URLs hinzu,
# die stattdessen ein leeres Array resolved (no data).
# Der Source-Patch (patch-encapsulated-pdf-frames.js) setzt zusaetzlich
# unsupported:true im dicom-pdf sopClassHandler, damit Prefetcher und
# HangingProtocol keine frames/1-Requests senden.
RUN for f in /usr/share/nginx/html/*.bundle.*.js; do \
      if grep -q 'else{var t=new Error("request failed")' "$f" 2>/dev/null; then \
        sed -i 's|else{var t=new Error("request failed")|else if(400===u.status\&\&u.responseURL\&\&u.responseURL.includes("/frames/"))r.verbose\&\&console.warn("No frames available (likely Encapsulated PDF): ",u.responseURL),c([]);else{var t=new Error("request failed")|g' "$f"; \
      fi; \
    done

# Eigene nginx-Konfiguration fuer SPA-Routing und Accession-Redirect.
COPY ohif-viewer/viewer-nginx.conf /etc/nginx/conf.d/default.conf

# Berechtigungen fuer nginx-User anpassen (cache, logs, pid)
RUN chown -R nginx:nginx /var/cache/nginx /var/run /var/log/nginx /run

EXPOSE 8080

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/ || exit 1

# nginx-Image hat bereits nginx-User (UID 101)
USER nginx

# nginx laeuft im Vordergrund.
CMD ["nginx", "-g", "daemon off;"]
