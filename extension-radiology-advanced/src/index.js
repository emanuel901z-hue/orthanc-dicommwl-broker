// Haupt-Einstiegspunkt der Extension.
// Registriert das Custom Attribute 'sameAs' und stellt Panel- und
// Command-Module zur Verfuegung.

import { id } from './id.js';
import sameAs from './sameAs.js';
import getPanelModule from './getPanelModule.js';
import getCommandsModule from './getCommandsModule.js';
import getHangingProtocolModule from './getHangingProtocolModule.js';

const extension = {
  id,

  // preRegistration wird beim Laden der Extension ausgefuehrt.
  // Hier registrieren wir das 'sameAs' Custom Attribute beim
  // HangingProtocolService, damit PET/CT-Fusion-Protokolle
  // ueber FrameOfReferenceUID matchen koennen.
  preRegistration: ({ servicesManager }) => {
    const { hangingProtocolService } = servicesManager.services;
    if (hangingProtocolService && hangingProtocolService.addCustomAttribute) {
      hangingProtocolService.addCustomAttribute(
        'sameAs',
        'Match an attribute in an existing display set',
        sameAs
      );
    }
  },

  getPanelModule,
  getCommandsModule,
  getHangingProtocolModule,
};

export default extension;
