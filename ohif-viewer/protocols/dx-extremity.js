/**
 * dx-extremity.js - Hanging Protocols fuer OHIF v3
 * Automatisch extrahiert aus default.js.
 *
 * Protokolle (16):
 *   - dx-elbow (Roentgen Ellenbogen)
 *   - dx-elbow-prior (Roentgen Ellenbogen mit VU)
 *   - dx-wrist (Roentgen Handgelenk)
 *   - dx-wrist-prior (Roentgen Handgelenk mit VU)
 *   - dx-knee (Roentgen Kniegelenk)
 *   - dx-knee-prior (Roentgen Kniegelenk mit VU)
 *   - dx-ankle (Roentgen Sprunggelenk)
 *   - dx-ankle-prior (Roentgen Sprunggelenk mit VU)
 *   - dx-foot (Roentgen Fuß)
 *   - dx-foot-prior (Roentgen Fuß mit VU)
 *   - dx-lower-leg (Roentgen Unterschenkel)
 *   - dx-lower-leg-prior (Roentgen Unterschenkel mit VU)
 *   - dx-sacrum (Roentgen Sacrum)
 *   - dx-sacrum-prior (Roentgen Sacrum mit VU)
 *   - dx-abdomen (Roentgen Abdomen leer)
 *   - dx-abdomen-prior (Roentgen Abdomen mit VU)
 */
module.exports = [
  {
    "id": "dx-elbow",
    "name": "Roentgen Ellenbogen",
    "locked": false,
    "isPreset": true,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "DX"
        },
        "required": true
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "Ellenbogen"
        },
        "weight": 15
      }
    ],
    "displaySetSelectors": {
      "elbow-vd": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Ellenbogen"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "VD"
            }
          }
        ]
      },
      "elbow-lat": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Ellenbogen"
            }
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
        "id": "dx-elbow-stage",
        "name": "Ellenbogen VD+LAT",
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
                "id": "elbow-vd"
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
                "id": "elbow-lat"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "dx-elbow-prior",
    "name": "Roentgen Ellenbogen mit VU",
    "locked": false,
    "isPreset": true,
    "numberOfPriorsReferenced": 1,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "DX"
        },
        "required": true
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "Ellenbogen"
        },
        "weight": 15
      }
    ],
    "displaySetSelectors": {
      "elbow-vd": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Ellenbogen"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "VD"
            }
          }
        ]
      },
      "elbow-lat": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Ellenbogen"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "LAT"
            }
          }
        ]
      },
      "prior-elbow-vd": {
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
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Ellenbogen"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "VD"
            }
          }
        ]
      },
      "prior-elbow-lat": {
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
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Ellenbogen"
            }
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
        "id": "dx-elbow-prior-stage",
        "name": "Ellenbogen + VU",
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
                "id": "elbow-vd"
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
                "id": "elbow-lat"
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
                "id": "prior-elbow-vd"
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
                "id": "prior-elbow-lat"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "dx-wrist",
    "name": "Roentgen Handgelenk",
    "locked": false,
    "isPreset": true,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "DX"
        },
        "required": true
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "Handgelenk"
        },
        "weight": 15
      }
    ],
    "displaySetSelectors": {
      "wrist-dv": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Handgelenk"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "DV"
            }
          }
        ]
      },
      "wrist-lat": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Handgelenk"
            }
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
        "id": "dx-wrist-stage",
        "name": "Handgelenk DV+LAT",
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
                "id": "wrist-dv"
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
                "id": "wrist-lat"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "dx-wrist-prior",
    "name": "Roentgen Handgelenk mit VU",
    "locked": false,
    "isPreset": true,
    "numberOfPriorsReferenced": 1,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "DX"
        },
        "required": true
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "Handgelenk"
        },
        "weight": 15
      }
    ],
    "displaySetSelectors": {
      "wrist-dv": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Handgelenk"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "DV"
            }
          }
        ]
      },
      "wrist-lat": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Handgelenk"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "LAT"
            }
          }
        ]
      },
      "prior-wrist-dv": {
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
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Handgelenk"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "DV"
            }
          }
        ]
      },
      "prior-wrist-lat": {
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
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Handgelenk"
            }
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
        "id": "dx-wrist-prior-stage",
        "name": "Handgelenk + VU",
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
                "id": "wrist-dv"
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
                "id": "wrist-lat"
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
                "id": "prior-wrist-dv"
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
                "id": "prior-wrist-lat"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "dx-knee",
    "name": "Roentgen Kniegelenk",
    "locked": false,
    "isPreset": true,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "DX"
        },
        "required": true
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "Knie"
        },
        "weight": 15
      }
    ],
    "displaySetSelectors": {
      "knee-ap": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Knie"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "AP"
            }
          }
        ]
      },
      "knee-lat": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Knie"
            }
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
        "id": "dx-knee-stage",
        "name": "Knie AP+LAT",
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
                "id": "knee-ap"
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
                "id": "knee-lat"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "dx-knee-prior",
    "name": "Roentgen Kniegelenk mit VU",
    "locked": false,
    "isPreset": true,
    "numberOfPriorsReferenced": 1,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "DX"
        },
        "required": true
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "Knie"
        },
        "weight": 15
      }
    ],
    "displaySetSelectors": {
      "knee-ap": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Knie"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "AP"
            }
          }
        ]
      },
      "knee-lat": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Knie"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "LAT"
            }
          }
        ]
      },
      "prior-knee-ap": {
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
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Knie"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "AP"
            }
          }
        ]
      },
      "prior-knee-lat": {
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
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Knie"
            }
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
        "id": "dx-knee-prior-stage",
        "name": "Knie + VU",
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
                "id": "knee-ap"
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
                "id": "knee-lat"
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
                "id": "prior-knee-ap"
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
                "id": "prior-knee-lat"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "dx-ankle",
    "name": "Roentgen Sprunggelenk",
    "locked": false,
    "isPreset": true,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "DX"
        },
        "required": true
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "Sprunggelenk"
        },
        "weight": 15
      }
    ],
    "displaySetSelectors": {
      "ankle-ap": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Sprunggelenk"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "AP"
            }
          }
        ]
      },
      "ankle-lat": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Sprunggelenk"
            }
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
        "id": "dx-ankle-stage",
        "name": "Sprunggelenk AP+LAT",
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
                "id": "ankle-ap"
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
                "id": "ankle-lat"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "dx-ankle-prior",
    "name": "Roentgen Sprunggelenk mit VU",
    "locked": false,
    "isPreset": true,
    "numberOfPriorsReferenced": 1,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "DX"
        },
        "required": true
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "Sprunggelenk"
        },
        "weight": 15
      }
    ],
    "displaySetSelectors": {
      "ankle-ap": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Sprunggelenk"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "AP"
            }
          }
        ]
      },
      "ankle-lat": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Sprunggelenk"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "LAT"
            }
          }
        ]
      },
      "prior-ankle-ap": {
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
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Sprunggelenk"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "AP"
            }
          }
        ]
      },
      "prior-ankle-lat": {
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
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Sprunggelenk"
            }
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
        "id": "dx-ankle-prior-stage",
        "name": "Sprunggelenk + VU",
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
                "id": "ankle-ap"
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
                "id": "ankle-lat"
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
                "id": "prior-ankle-ap"
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
                "id": "prior-ankle-lat"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "dx-foot",
    "name": "Roentgen Fuß",
    "locked": false,
    "isPreset": true,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "DX"
        },
        "required": true
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "Fuß"
        },
        "weight": 15
      }
    ],
    "displaySetSelectors": {
      "foot-dp": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Fuß"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "dp"
            }
          }
        ]
      },
      "foot-schraeg": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Fuß"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "schräg"
            }
          }
        ]
      }
    },
    "stages": [
      {
        "id": "dx-foot-stage",
        "name": "Fuß dp+schraeg",
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
                "id": "foot-dp"
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
                "id": "foot-schraeg"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "dx-foot-prior",
    "name": "Roentgen Fuß mit VU",
    "locked": false,
    "isPreset": true,
    "numberOfPriorsReferenced": 1,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "DX"
        },
        "required": true
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "Fuß"
        },
        "weight": 15
      }
    ],
    "displaySetSelectors": {
      "foot-dp": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Fuß"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "dp"
            }
          }
        ]
      },
      "foot-schraeg": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Fuß"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "schräg"
            }
          }
        ]
      },
      "prior-foot-dp": {
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
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Fuß"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "dp"
            }
          }
        ]
      },
      "prior-foot-schraeg": {
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
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Fuß"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "schräg"
            }
          }
        ]
      }
    },
    "stages": [
      {
        "id": "dx-foot-prior-stage",
        "name": "Fuß + VU",
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
                "id": "foot-dp"
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
                "id": "foot-schraeg"
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
                "id": "prior-foot-dp"
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
                "id": "prior-foot-schraeg"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "dx-lower-leg",
    "name": "Roentgen Unterschenkel",
    "locked": false,
    "isPreset": true,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "DX"
        },
        "required": true
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "Unterschenkel"
        },
        "weight": 15
      }
    ],
    "displaySetSelectors": {
      "ll-ap": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Unterschenkel"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "AP"
            }
          }
        ]
      },
      "ll-lat": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Unterschenkel"
            }
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
        "id": "dx-lower-leg-stage",
        "name": "Unterschenkel AP+LAT",
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
                "id": "ll-ap"
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
                "id": "ll-lat"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "dx-lower-leg-prior",
    "name": "Roentgen Unterschenkel mit VU",
    "locked": false,
    "isPreset": true,
    "numberOfPriorsReferenced": 1,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "DX"
        },
        "required": true
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "Unterschenkel"
        },
        "weight": 15
      }
    ],
    "displaySetSelectors": {
      "ll-ap": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Unterschenkel"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "AP"
            }
          }
        ]
      },
      "ll-lat": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Unterschenkel"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "LAT"
            }
          }
        ]
      },
      "prior-ll-ap": {
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
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Unterschenkel"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "AP"
            }
          }
        ]
      },
      "prior-ll-lat": {
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
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Unterschenkel"
            }
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
        "id": "dx-lower-leg-prior-stage",
        "name": "Unterschenkel + VU",
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
                "id": "ll-ap"
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
                "id": "ll-lat"
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
                "id": "prior-ll-ap"
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
                "id": "prior-ll-lat"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "dx-sacrum",
    "name": "Roentgen Sacrum",
    "locked": false,
    "isPreset": true,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "DX"
        },
        "required": true
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "Sacrum"
        },
        "weight": 15
      }
    ],
    "displaySetSelectors": {
      "sacrum-lat": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Sacrum"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "LAT"
            }
          }
        ]
      },
      "sacrum-ap": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Sacrum"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "AP"
            }
          }
        ]
      }
    },
    "stages": [
      {
        "id": "dx-sacrum-stage",
        "name": "Sacrum LAT+AP",
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
                "id": "sacrum-lat"
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
                "id": "sacrum-ap"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "dx-sacrum-prior",
    "name": "Roentgen Sacrum mit VU",
    "locked": false,
    "isPreset": true,
    "numberOfPriorsReferenced": 1,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "DX"
        },
        "required": true
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "Sacrum"
        },
        "weight": 15
      }
    ],
    "displaySetSelectors": {
      "sacrum-lat": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Sacrum"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "LAT"
            }
          }
        ]
      },
      "sacrum-ap": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Sacrum"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "AP"
            }
          }
        ]
      },
      "prior-sacrum-lat": {
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
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Sacrum"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "LAT"
            }
          }
        ]
      },
      "prior-sacrum-ap": {
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
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Sacrum"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "AP"
            }
          }
        ]
      }
    },
    "stages": [
      {
        "id": "dx-sacrum-prior-stage",
        "name": "Sacrum + VU",
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
                "id": "sacrum-lat"
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
                "id": "sacrum-ap"
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
                "id": "prior-sacrum-lat"
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
                "id": "prior-sacrum-ap"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "dx-abdomen",
    "name": "Roentgen Abdomen leer",
    "locked": false,
    "isPreset": true,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "DX"
        },
        "required": true
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "Abdomen"
        },
        "weight": 15
      }
    ],
    "displaySetSelectors": {
      "abd-pa": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Abdomen"
            }
          }
        ]
      }
    },
    "stages": [
      {
        "id": "dx-abdomen-stage",
        "name": "Abdomen PA",
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
                "id": "abd-pa"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "dx-abdomen-prior",
    "name": "Roentgen Abdomen mit VU",
    "locked": false,
    "isPreset": true,
    "numberOfPriorsReferenced": 1,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "DX"
        },
        "required": true
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "Abdomen"
        },
        "weight": 15
      }
    ],
    "displaySetSelectors": {
      "abd-pa": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Abdomen"
            }
          }
        ]
      },
      "prior-abd-pa": {
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
              "equals": "DX"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Abdomen"
            }
          }
        ]
      }
    },
    "stages": [
      {
        "id": "dx-abdomen-prior-stage",
        "name": "Abdomen + VU",
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
                "id": "abd-pa"
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
                "id": "prior-abd-pa"
              }
            ]
          }
        ]
      }
    ]
  }
];
