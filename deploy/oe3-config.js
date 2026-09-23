// Runtime config for the workspace stack (mounted over dist/config.js).
window.__OE3_CONFIG__ = {
  orthancUrl: "/orthanc-proxy",
  brokerUrl: "/broker-api",
  authMode: "none",
  // No backend proxy in this stack — skip the /oe3-me gate (local admin).
  authCheck: false,
  // …and skip the viewer-session POST (endpoint only exists behind the proxy).
  viewerSession: false,
  features: {
    enableMwlBroker: true,
    // Orthanc's own worklists plugin REST API is off in this stack (the MWL
    // broker serves the modalities) — the page is hidden while this is false.
    enableWorklists: false,
    enableModalityConfig: true,
    enableUpload: true,
  },
  // Die Viewer-Liste kann hier vorgegeben und mit viewersLocked: true
  // schreibgeschützt werden — siehe orthanc-explorer-3-usable/docs/oe3-standalone.md
  // viewers: [{ id: "ohif", url: "/ohif/viewer", enabled: true }],
  // viewersLocked: false,
  branding: { title: "MWL Broker Console", logoUrl: "/logo/oe3-logo-128.png" },
};
