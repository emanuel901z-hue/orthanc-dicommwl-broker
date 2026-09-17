/**
 * Runtime-Konfiguration des OHIF-Viewers fuer diesen Stack.
 *
 * Wird vom docker-compose ueber die im Image eingebaute Datei gemountet
 * (config/default.js) — gleiches Muster wie deploy/oe3-config.js. Aenderungen
 * hier wirken nach einem Container-Restart, ohne das Image neu zu bauen.
 *
 * DICOMweb laeuft same-origin ueber den OE3-nginx: /orthanc-proxy/dicom-web
 * zeigt auf das DICOMweb-Plugin des mitgelieferten Orthanc.
 */
window.config = {
  routerBasename: '/ohif/',
  showStudyList: false,
  showLoadingIndicator: true,
  studyListFunctionsEnabled: false,
  defaultDataSourceName: 'dicomweb',
  showPatientInfo: 'visibleReadOnly',
  studyPrefetcher: {
    enabled: true,
    displaySetsCount: 2,
    maxNumPrefetchRequests: 10,
    order: 'closest',
  },
  maxNumRequests: {
    interaction: 15,
    thumbnail: 10,
    prefetch: 5,
  },
  extensions: [],
  modes: [],
  investigationalUseDialog: { option: 'never' },
  dataSources: [
    {
      namespace: '@ohif/extension-default.dataSourcesModule.dicomweb',
      sourceName: 'dicomweb',
      configuration: {
        friendlyName: 'Orthanc DICOMweb',
        name: 'dicomweb',
        qidoRoot: '/orthanc-proxy/dicom-web',
        wadoRoot: '/orthanc-proxy/dicom-web',
        wadoUriRoot: '/orthanc-proxy/dicom-web',
        qidoSupportsIncludeField: false,
        qidoSupportsFuzzyMatching: false,
        supportsFuzzyMatching: false,
        imageRendering: 'wadors',
        thumbnailRendering: 'wadors',
        studyInstanceUid: true,
        seriesInstanceUid: true,
        sopInstanceUid: true,
        enableStudyLazyLoad: true,
        supportsReject: false,
        omitQuotationForMultipartRequest: true,
        staticWado: false,
        queryLimit: 100,
        requestOptions: { headers: {} },
      },
    },
  ],
};
