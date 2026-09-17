/**
 * xa-dsa.js - Hanging Protocols fuer OHIF v3
 * Automatisch extrahiert aus default.js.
 *
 * Protokolle (7):
 *   - xa-default (DSA Default)
 *   - xa-dsa-head (DSA Hirnangiographie)
 *   - xa-dsa-head-prior (DSA Hirnangiographie mit VU)
 *   - xa-dsa-carotid (DSA Karotis)
 *   - xa-dsa-aorta (DSA Aorta)
 *   - xa-dsa-peripheral (DSA Peripher (Becken-Bein))
 *   - xa-dsa-coronary (DSA Coronary (Herzkatheter))
 */
module.exports = [
  {
    "id": "xa-default",
    "name": "DSA Default",
    "locked": false,
    "isPreset": true,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "XA"
        },
        "required": true
      }
    ],
    "displaySetSelectors": {
      "xa-first": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "XA"
            },
            "required": true
          }
        ]
      }
    },
    "stages": [
      {
        "id": "xa-default-stage",
        "name": "DSA 1x1",
        "viewportStructure": {
          "layoutType": "grid",
          "properties": {
            "rows": 1,
            "columns": 1
          }
        },
        "viewports": [
          {
            "viewportOptions": {
              "viewportType": "stack",
              "toolGroupId": "default"
            },
            "displaySets": [
              {
                "id": "xa-first"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "xa-dsa-head",
    "name": "DSA Hirnangiographie",
    "locked": false,
    "isPreset": true,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "XA"
        },
        "required": true
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "Hirn"
        },
        "weight": 20
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "zerebral"
        },
        "weight": 20
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "Carotis"
        },
        "weight": 15
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "cerebri"
        },
        "weight": 15
      }
    ],
    "displaySetSelectors": {
      "dsa-ap": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "XA"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "AP"
            }
          }
        ]
      },
      "dsa-lat": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "XA"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "LAT"
            }
          }
        ]
      },
      "dsa-1": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "XA"
            },
            "required": true
          }
        ]
      },
      "dsa-2": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "XA"
            },
            "required": true
          }
        ]
      }
    },
    "stages": [
      {
        "id": "xa-dsa-head-stage",
        "name": "DSA Hirn 2x2",
        "viewportStructure": {
          "layoutType": "grid",
          "properties": {
            "rows": 2,
            "columns": 2
          }
        },
        "viewports": [
          {
            "viewportOptions": {
              "viewportType": "stack",
              "toolGroupId": "default"
            },
            "displaySets": [
              {
                "id": "dsa-ap"
              }
            ]
          },
          {
            "viewportOptions": {
              "viewportType": "stack",
              "toolGroupId": "default"
            },
            "displaySets": [
              {
                "id": "dsa-lat"
              }
            ]
          },
          {
            "viewportOptions": {
              "viewportType": "stack",
              "toolGroupId": "default"
            },
            "displaySets": [
              {
                "id": "dsa-1"
              }
            ]
          },
          {
            "viewportOptions": {
              "viewportType": "stack",
              "toolGroupId": "default"
            },
            "displaySets": [
              {
                "id": "dsa-2"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "xa-dsa-head-prior",
    "name": "DSA Hirnangiographie mit VU",
    "locked": false,
    "isPreset": true,
    "numberOfPriorsReferenced": 1,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "XA"
        },
        "required": true
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "Hirn"
        },
        "weight": 20
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "zerebral"
        },
        "weight": 20
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "Carotis"
        },
        "weight": 15
      }
    ],
    "displaySetSelectors": {
      "dsa-ap": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "XA"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "AP"
            }
          }
        ]
      },
      "dsa-lat": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "XA"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "LAT"
            }
          }
        ]
      },
      "prior-dsa-ap": {
        "studyMatchingRules": [
          {
            "attribute": "priorInstance",
            "constraint": {
              "equals": 1
            }
          }
        ],
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "XA"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "AP"
            }
          }
        ]
      },
      "prior-dsa-lat": {
        "studyMatchingRules": [
          {
            "attribute": "priorInstance",
            "constraint": {
              "equals": 1
            }
          }
        ],
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "XA"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "LAT"
            }
          }
        ]
      }
    },
    "stages": [
      {
        "id": "xa-dsa-head-prior-stage",
        "name": "DSA Hirn + VU",
        "viewportStructure": {
          "layoutType": "grid",
          "properties": {
            "rows": 2,
            "columns": 2
          }
        },
        "viewports": [
          {
            "viewportOptions": {
              "viewportType": "stack",
              "toolGroupId": "default"
            },
            "displaySets": [
              {
                "id": "dsa-ap"
              }
            ]
          },
          {
            "viewportOptions": {
              "viewportType": "stack",
              "toolGroupId": "default"
            },
            "displaySets": [
              {
                "id": "dsa-lat"
              }
            ]
          },
          {
            "viewportOptions": {
              "viewportType": "stack",
              "toolGroupId": "default"
            },
            "displaySets": [
              {
                "id": "prior-dsa-ap"
              }
            ]
          },
          {
            "viewportOptions": {
              "viewportType": "stack",
              "toolGroupId": "default"
            },
            "displaySets": [
              {
                "id": "prior-dsa-lat"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "xa-dsa-carotid",
    "name": "DSA Karotis",
    "locked": false,
    "isPreset": true,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "XA"
        },
        "required": true
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "Carotis"
        },
        "weight": 20
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "Karotis"
        },
        "weight": 20
      }
    ],
    "displaySetSelectors": {
      "dsa-ap": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "XA"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "AP"
            }
          }
        ]
      },
      "dsa-lat": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "XA"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "LAT"
            }
          }
        ]
      }
    },
    "stages": [
      {
        "id": "xa-dsa-carotid-stage",
        "name": "DSA Karotis 1x2",
        "viewportStructure": {
          "layoutType": "grid",
          "properties": {
            "rows": 1,
            "columns": 2
          }
        },
        "viewports": [
          {
            "viewportOptions": {
              "viewportType": "stack",
              "toolGroupId": "default"
            },
            "displaySets": [
              {
                "id": "dsa-ap"
              }
            ]
          },
          {
            "viewportOptions": {
              "viewportType": "stack",
              "toolGroupId": "default"
            },
            "displaySets": [
              {
                "id": "dsa-lat"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "xa-dsa-aorta",
    "name": "DSA Aorta",
    "locked": false,
    "isPreset": true,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "XA"
        },
        "required": true
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "Aorta"
        },
        "weight": 20
      }
    ],
    "displaySetSelectors": {
      "dsa-ap": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "XA"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "AP"
            }
          }
        ]
      },
      "dsa-lat": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "XA"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "LAT"
            }
          }
        ]
      }
    },
    "stages": [
      {
        "id": "xa-dsa-aorta-stage",
        "name": "DSA Aorta 1x2",
        "viewportStructure": {
          "layoutType": "grid",
          "properties": {
            "rows": 1,
            "columns": 2
          }
        },
        "viewports": [
          {
            "viewportOptions": {
              "viewportType": "stack",
              "toolGroupId": "default"
            },
            "displaySets": [
              {
                "id": "dsa-ap"
              }
            ]
          },
          {
            "viewportOptions": {
              "viewportType": "stack",
              "toolGroupId": "default"
            },
            "displaySets": [
              {
                "id": "dsa-lat"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "xa-dsa-peripheral",
    "name": "DSA Peripher (Becken-Bein)",
    "locked": false,
    "isPreset": true,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "XA"
        },
        "required": true
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "Peripher"
        },
        "weight": 20
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "Becken"
        },
        "weight": 15
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "Bein"
        },
        "weight": 15
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "Femoral"
        },
        "weight": 15
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "Poplitea"
        },
        "weight": 15
      }
    ],
    "displaySetSelectors": {
      "dsa-1": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "XA"
            },
            "required": true
          }
        ]
      },
      "dsa-2": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "XA"
            },
            "required": true
          }
        ]
      }
    },
    "stages": [
      {
        "id": "xa-dsa-peripheral-stage",
        "name": "DSA Peripher 1x2",
        "viewportStructure": {
          "layoutType": "grid",
          "properties": {
            "rows": 1,
            "columns": 2
          }
        },
        "viewports": [
          {
            "viewportOptions": {
              "viewportType": "stack",
              "toolGroupId": "default"
            },
            "displaySets": [
              {
                "id": "dsa-1"
              }
            ]
          },
          {
            "viewportOptions": {
              "viewportType": "stack",
              "toolGroupId": "default"
            },
            "displaySets": [
              {
                "id": "dsa-2"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "xa-dsa-coronary",
    "name": "DSA Coronary (Herzkatheter)",
    "locked": false,
    "isPreset": true,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "XA"
        },
        "required": true
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "Coronary"
        },
        "weight": 20
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "Koronar"
        },
        "weight": 20
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "Herz"
        },
        "weight": 15
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "LAD"
        },
        "weight": 15
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "RCA"
        },
        "weight": 15
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "CX"
        },
        "weight": 15
      }
    ],
    "displaySetSelectors": {
      "dsa-1": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "XA"
            },
            "required": true
          }
        ]
      },
      "dsa-2": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "XA"
            },
            "required": true
          }
        ]
      }
    },
    "stages": [
      {
        "id": "xa-dsa-coronary-stage",
        "name": "DSA Coronary 1x2",
        "viewportStructure": {
          "layoutType": "grid",
          "properties": {
            "rows": 1,
            "columns": 2
          }
        },
        "viewports": [
          {
            "viewportOptions": {
              "viewportType": "stack",
              "toolGroupId": "default"
            },
            "displaySets": [
              {
                "id": "dsa-1"
              }
            ]
          },
          {
            "viewportOptions": {
              "viewportType": "stack",
              "toolGroupId": "default"
            },
            "displaySets": [
              {
                "id": "dsa-2"
              }
            ]
          }
        ]
      }
    ]
  }
];
