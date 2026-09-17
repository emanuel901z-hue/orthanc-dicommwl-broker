/**
 * dx-skeleton.js - Hanging Protocols fuer OHIF v3
 * Automatisch extrahiert aus default.js.
 *
 * Protokolle (9):
 *   - dx-thorax (Roentgen Thorax)
 *   - dx-thorax-prior (Roentgen Thorax mit VU)
 *   - dx-spine (Roentgen Wirbelsaeule)
 *   - dx-spine-prior (Roentgen WS mit VU)
 *   - dx-extremity (Roentgen Extremitaet)
 *   - dx-hand (Roentgen Hand)
 *   - dx-hand-prior (Roentgen Hand mit VU)
 *   - dx-pelvis (Roentgen Becken)
 *   - dx-pelvis-prior (Roentgen Becken mit VU)
 */
module.exports = [
  {
    "id": "dx-thorax",
    "name": "Roentgen Thorax",
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
          "contains": "Thorax"
        },
        "weight": 10
      }
    ],
    "displaySetSelectors": {
      "thx-pa": {
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
              "contains": "Thorax"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "PA"
            }
          }
        ]
      },
      "thx-lat": {
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
              "contains": "Thorax"
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
        "id": "dx-thorax-stage",
        "name": "Thorax PA+LAT",
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
                "id": "thx-pa"
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
                "id": "thx-lat"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "dx-thorax-prior",
    "name": "Roentgen Thorax mit VU",
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
          "contains": "Thorax"
        },
        "weight": 10
      }
    ],
    "displaySetSelectors": {
      "thx-pa": {
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
              "contains": "Thorax"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "PA"
            }
          }
        ]
      },
      "thx-lat": {
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
              "contains": "Thorax"
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
      "prior-thx-pa": {
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
              "contains": "Thorax"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "PA"
            }
          }
        ]
      },
      "prior-thx-lat": {
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
              "contains": "Thorax"
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
        "id": "dx-thorax-prior-stage",
        "name": "Thorax + VU",
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
                "id": "thx-pa"
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
                "id": "thx-lat"
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
                "id": "prior-thx-pa"
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
                "id": "prior-thx-lat"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "dx-spine",
    "name": "Roentgen Wirbelsaeule",
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
          "contains": "WS"
        },
        "weight": 10
      }
    ],
    "displaySetSelectors": {
      "spine-ap": {
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
              "contains": "WS"
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
      "spine-lat": {
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
              "contains": "WS"
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
        "id": "dx-spine-stage",
        "name": "WS AP+LAT",
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
                "id": "spine-ap"
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
                "id": "spine-lat"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "dx-spine-prior",
    "name": "Roentgen WS mit VU",
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
          "contains": "WS"
        },
        "weight": 10
      }
    ],
    "displaySetSelectors": {
      "spine-ap": {
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
              "contains": "WS"
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
      "spine-lat": {
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
              "contains": "WS"
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
      "prior-spine-ap": {
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
              "contains": "WS"
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
      "prior-spine-lat": {
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
              "contains": "WS"
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
        "id": "dx-spine-prior-stage",
        "name": "WS + VU",
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
                "id": "spine-ap"
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
                "id": "spine-lat"
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
                "id": "prior-spine-ap"
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
                "id": "prior-spine-lat"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "dx-extremity",
    "name": "Roentgen Extremitaet",
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
          "contains": "AP"
        },
        "weight": 5
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "contains": "LAT"
        },
        "weight": 5
      }
    ],
    "displaySetSelectors": {
      "ext-ap": {
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
              "contains": "AP"
            }
          }
        ]
      },
      "ext-lat": {
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
              "contains": "LAT"
            }
          }
        ]
      }
    },
    "stages": [
      {
        "id": "dx-extremity-stage",
        "name": "AP+LAT",
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
                "id": "ext-ap"
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
                "id": "ext-lat"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "dx-hand",
    "name": "Roentgen Hand",
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
          "contains": "Hand"
        },
        "weight": 10
      }
    ],
    "displaySetSelectors": {
      "hand-ap": {
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
              "contains": "Hand"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "ap"
            }
          }
        ]
      },
      "hand-schraeg": {
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
              "contains": "Hand"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "schraeg"
            }
          }
        ]
      },
      "hand-dv": {
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
              "contains": "Hand"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "DV"
            }
          }
        ]
      }
    },
    "stages": [
      {
        "id": "dx-hand-stage",
        "name": "Hand 1x3",
        "viewportStructure": {
          "layoutType": "grid",
          "properties": {
            "rows": 1,
            "columns": 3
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
                "id": "hand-ap"
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
                "id": "hand-schraeg"
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
                "id": "hand-dv"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "dx-hand-prior",
    "name": "Roentgen Hand mit VU",
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
          "contains": "Hand"
        },
        "weight": 10
      }
    ],
    "displaySetSelectors": {
      "hand-ap": {
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
              "contains": "Hand"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "ap"
            }
          }
        ]
      },
      "hand-schraeg": {
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
              "contains": "Hand"
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
      "hand-dv": {
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
              "contains": "Hand"
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
      "prior-hand-ap": {
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
              "contains": "Hand"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "ap"
            }
          }
        ]
      },
      "prior-hand-schraeg": {
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
              "contains": "Hand"
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
      "prior-hand-dv": {
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
              "contains": "Hand"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "DV"
            }
          }
        ]
      }
    },
    "stages": [
      {
        "id": "dx-hand-prior-stage",
        "name": "Hand + VU",
        "viewportStructure": {
          "layoutType": "grid",
          "properties": {
            "rows": 2,
            "columns": 3
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
                "id": "hand-ap"
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
                "id": "hand-schraeg"
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
                "id": "hand-dv"
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
                "id": "prior-hand-ap"
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
                "id": "prior-hand-schraeg"
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
                "id": "prior-hand-dv"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "dx-pelvis",
    "name": "Roentgen Becken",
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
          "contains": "Becken"
        },
        "weight": 10
      }
    ],
    "displaySetSelectors": {
      "becken-ap": {
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
              "contains": "Becken"
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
      "huefte-lauenstein": {
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
              "contains": "Hueftgelenk"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Lauenstein"
            }
          }
        ]
      }
    },
    "stages": [
      {
        "id": "dx-pelvis-stage",
        "name": "Becken 2x1",
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
                "id": "becken-ap"
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
                "id": "huefte-lauenstein"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "dx-pelvis-prior",
    "name": "Roentgen Becken mit VU",
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
          "contains": "Becken"
        },
        "weight": 10
      }
    ],
    "displaySetSelectors": {
      "becken-ap": {
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
              "contains": "Becken"
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
      "huefte-lauenstein": {
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
              "contains": "Hüftgelenk"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Lauenstein"
            }
          }
        ]
      },
      "prior-becken-ap": {
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
              "contains": "Becken"
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
      "prior-huefte-lauenstein": {
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
              "contains": "Hüftgelenk"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "contains": "Lauenstein"
            }
          }
        ]
      }
    },
    "stages": [
      {
        "id": "dx-pelvis-prior-stage",
        "name": "Becken + VU",
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
                "id": "becken-ap"
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
                "id": "huefte-lauenstein"
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
                "id": "prior-becken-ap"
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
                "id": "prior-huefte-lauenstein"
              }
            ]
          }
        ]
      }
    ]
  }
];
