/**
 * static-config.js - Statische OHIF-App-Konfiguration fuer Pulmopath
 *
 * Angepasst fuer Orthanc DICOMweb (TEMP-PACS) mit JWT-Auth via Backend-Proxy.
 * DICOMweb-Pfade zeigen auf /api/v1/pacs/orthanc/dicom-web (authentifiziert).
 *
 * Multi-Tenant-Isolation wird durch den Backend-Proxy gewaehrleistet
 * (enforcePatientPacsAccess / enforceStaffPacsAccess Middleware).
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
        "friendlyName": "Orthanc DICOMweb (Pulmopath)",
        "name": "dicomweb",
        "qidoRoot": "/api/v1/pacs/orthanc/dicom-web",
        "wadoRoot": "/api/v1/pacs/orthanc/dicom-web",
        "wadoUriRoot": "/api/v1/pacs/orthanc/dicom-web",
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
