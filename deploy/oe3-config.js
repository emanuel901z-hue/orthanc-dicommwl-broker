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
    enableModalityConfig: true,
    enableUpload: true,
  },
  branding: { title: "MWL Broker Console", logoUrl: "/logo/oe3-logo-128.png" },
};
