// getHangingProtocolModule.js - Registriert alle custom Hanging Protocols
// beim HangingProtocolService.
//
// OHIF v3 registriert Hanging Protocols NICHT aus window.config.hangingProtocols,
// sondern ueber getHangingProtocolModule der Extensions. Die Default-Extension
// registriert nur 6 Basis-Protokolle (default, compare, mammo, scale, MxN, MxN8).
// Diese Extension registriert alle custom Protokolle aus ohif-viewer/protocols/.
//
// Die Protokoll-Dateien werden beim Docker-Build in src/hangingProtocols/
// kopiert und als ES-Module importiert.

import ctDefault from './hangingProtocols/generic.js';
import ctCranial from './hangingProtocols/ct-cranial.js';
import ctAngio from './hangingProtocols/ct-angio.js';
import ctBodyTrauma from './hangingProtocols/ct-body-trauma.js';
import dxSkeleton from './hangingProtocols/dx-skeleton.js';
import dxExtremity from './hangingProtocols/dx-extremity.js';
import mr from './hangingProtocols/mr.js';
import mrNeuro from './hangingProtocols/mr-neuro.js';
import mrMsk from './hangingProtocols/mr-msk.js';
import mrAbdomen from './hangingProtocols/mr-abdomen.js';
import mrBba from './hangingProtocols/mr-bba.js';
import xaDsa from './hangingProtocols/xa-dsa.js';

const allProtocols = [
  ...ctDefault,
  ...ctCranial,
  ...ctAngio,
  ...ctBodyTrauma,
  ...dxSkeleton,
  ...dxExtremity,
  ...mr,
  ...mrNeuro,
  ...mrMsk,
  ...mrAbdomen,
  ...mrBba,
  ...xaDsa,
];

function getHangingProtocolModule() {
  return allProtocols.map(protocol => ({
    name: protocol.id,
    protocol,
  }));
}

export default getHangingProtocolModule;
