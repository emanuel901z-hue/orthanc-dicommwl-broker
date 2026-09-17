/**
 * static-config.js - Statische OHIF-App-Konfiguration
 *
 * Angepasst fuer den mwl-broker-Stack: DICOMweb kommt aus dem mitgelieferten
 * Orthanc (DICOMweb-Plugin), same-origin ueber den OE3-nginx
 * (/orthanc-proxy/dicom-web). Kein pacs-proxy, keine metadata-bridge,
 * kein API-Key — der Stack laeuft in einem isolierten Docker-Netz.
 *
 * Der Viewer wird unter /ohif/ ausgeliefert (routerBasename) und ist damit
 * direkt aus OE3 erreichbar ("Open in OHIF" -> /ohif/viewer?StudyInstanceUIDs=).
 *
 * Zur Laufzeit kann die Config ueber eine gemountete Datei ersetzt werden
 * (siehe deploy/ohif-config.js im Workspace-Root).
 */
module.exports = {
  "routerBasename": "/ohif/",
  "showStudyList": false,
  "showLoadingIndicator": true,
  "studyListFunctionsEnabled": false,
  "defaultDataSourceName": "dicomweb",
  "showPatientInfo": "visibleReadOnly",
  "studyPrefetcher": {
    "enabled": true,
    "displaySetsCount": 2,
    "maxNumPrefetchRequests": 10,
    "order": "closest"
  },
  "maxNumRequests": {
    "interaction": 15,
    "thumbnail": 10,
    "prefetch": 5
  },
  "extensions": [],
  "modes": [],
  "investigationalUseDialog": {
    "option": "never"
  },
  "dataSources": [
    {
      "namespace": "@ohif/extension-default.dataSourcesModule.dicomweb",
      "sourceName": "dicomweb",
      "configuration": {
        "friendlyName": "Orthanc DICOMweb",
        "name": "dicomweb",
        "qidoRoot": "/orthanc-proxy/dicom-web",
        "wadoRoot": "/orthanc-proxy/dicom-web",
        "wadoUriRoot": "/orthanc-proxy/dicom-web",
        "qidoSupportsIncludeField": false,
        "qidoSupportsFuzzyMatching": false,
        "supportsFuzzyMatching": false,
        "imageRendering": "wadors",
        "thumbnailRendering": "wadors",
        "studyInstanceUid": true,
        "seriesInstanceUid": true,
        "sopInstanceUid": true,
        "enableStudyLazyLoad": true,
        "supportsReject": false,
        "omitQuotationForMultipartRequest": true,
        "staticWado": false,
        "queryLimit": 100,
        "requestOptions": {
          "headers": {}
        }
      }
    }
  ]
};
