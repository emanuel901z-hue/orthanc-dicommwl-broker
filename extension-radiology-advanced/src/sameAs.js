// sameAs - Custom Attribute fuer Hanging Protocol Matching.
//
// Ermöglicht das Matching von DisplaySets ueber gemeinsame Attribute,
// z.B. FrameOfReferenceUID fuer PET/CT-Fusion. Die Rule muss zusaetzlich
// sameAttribute und sameDisplaySetId enthalten:
//
//   {
//     attribute: 'sameAs',
//     sameAttribute: 'FrameOfReferenceUID',
//     sameDisplaySetId: 'ctDisplaySet',
//     constraint: { equals: { value: true } }
//   }
//
// Der Callback vergleicht das Attribut des aktuellen DisplaySets mit
// dem des bereits gematchten DisplaySets (sameDisplaySetId).

function sameAs(instance, servicesManager, context) {
  // Der context kann das Rule-Objekt oder ein Wrapper enthalten.
  // Wir versuchen, sameAttribute und sameDisplaySetId zu extrahieren.
  let sameAttribute = null;
  let sameDisplaySetId = null;

  if (context && typeof context === 'object') {
    sameAttribute = context.sameAttribute;
    sameDisplaySetId = context.sameDisplaySetId;
  }

  // Wenn wir keine Rule-Parameter haben, geben wir den
  // FrameOfReferenceUID des Instances zurueck, damit die
  // Constraint-Pruefung durch den HPMatcher erfolgen kann.
  if (!sameAttribute || !sameDisplaySetId) {
    return instance?.FrameOfReferenceUID ?? null;
  }

  const { displaySetService, hangingProtocolService } =
    servicesManager?.services || {};

  // Versuche, die bereits gematchten DisplaySets zu finden.
  // OHIF speichert diese im HangingProtocolService oder im
  // aktuellen Matching-Kontext.
  let matchedDisplaySets = null;
  if (hangingProtocolService) {
    matchedDisplaySets =
      hangingProtocolService._matchedDisplaySets ||
      hangingProtocolService.matchedDisplaySets ||
      hangingProtocolService?.protocolEngine?._matchedDisplaySets ||
      null;
  }

  if (!matchedDisplaySets || !matchedDisplaySets[sameDisplaySetId]) {
    // Fallback: ueber displaySetService nach DisplaySet mit
    // passender Modality suchen.
    if (displaySetService) {
      const allDisplaySets = displaySetService.getActiveDisplaySets();
      const other = allDisplaySets.find(
        ds => ds.displaySetSelectorId === sameDisplaySetId
      );
      if (other && instance && other[sameAttribute]) {
        return instance[sameAttribute] === other[sameAttribute];
      }
    }
    return false;
  }

  const otherDisplaySet = matchedDisplaySets[sameDisplaySetId];
  if (!instance || !otherDisplaySet) {
    return false;
  }

  return instance[sameAttribute] === otherDisplaySet[sameAttribute];
}

export default sameAs;
