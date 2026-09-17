/**
 * ct-body-trauma.js - Hanging Protocols fuer OHIF v3
 * CT Body/Trauma Protokolle, optimiert fuer PACS-Realitaet.
 *
 * Protokolle (14):
 *   - ct-hws (CT HWS)
 *   - ct-hws-prior (CT HWS mit VU)
 *   - ct-thorax-abdomen (CT Thorax/Abdomen)
 *   - ct-thorax-abdomen-prior (CT Thorax/Abdomen mit VU)
 *   - ct-ctab-spine (CT Thorax/Abdomen + WS)
 *   - ct-ctab-spine-prior (CT Thorax/Abd + WS mit VU)
 *   - ct-mittelgesicht (CT Mittelgesicht)
 *   - ct-mittelgesicht-prior (CT Mittelgesicht mit VU)
 *   - ct-abdomen (CT Abdomen)
 *   - ct-abdomen-prior (CT Abdomen mit VU)
 *   - ct-osteo (CT Osteo (Extremitaeten))
 *   - ct-osteo-prior (CT Osteo mit VU)
 *   - ct-polytrauma (CT Polytrauma)
 *   - ct-polytrauma-prior (CT Polytrauma mit VU)
 */
module.exports = [
  {
    "id": "ct-hws",
    "name": "CT HWS",
    "locked": false,
    "isPreset": true,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "CT"
        },
        "required": true
      },
      {
        "attribute": "StudyDescription",
        "constraint": {
          "containsI": "HWS"
        },
        "weight": 10
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "HWS"
        },
        "weight": 10
      }
    ],
    "displaySetSelectors": {
      "hws-wt": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "HWS"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "WT"
            }
          }
        ]
      },
      "hws-kf": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "HWS"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "KF"
            }
          }
        ]
      },
      "hws-sag": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "HWS"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "sag"
            }
          }
        ]
      },
      "hws-cor": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "HWS"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": ["cor", "kor"]
            }
          }
        ]
      }
    },
    "stages": [
      {
        "id": "ct-hws-stage",
        "name": "HWS 2x2",
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
                "id": "hws-wt"
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
                "id": "hws-sag"
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
                "id": "hws-cor"
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
                "id": "hws-kf"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "ct-hws-prior",
    "name": "CT HWS mit VU",
    "locked": false,
    "isPreset": true,
    "numberOfPriorsReferenced": 1,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "CT"
        },
        "required": true
      },
      {
        "attribute": "StudyDescription",
        "constraint": {
          "containsI": "HWS"
        },
        "weight": 10
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "HWS"
        },
        "weight": 10
      }
    ],
    "displaySetSelectors": {
      "hws-wt": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "HWS"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "WT"
            }
          }
        ]
      },
      "hws-kf": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "HWS"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "KF"
            }
          }
        ]
      },
      "hws-sag": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "HWS"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "sag"
            }
          }
        ]
      },
      "hws-cor": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "HWS"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": ["cor", "kor"]
            }
          }
        ]
      },
      "prior-hws-wt": {
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
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "HWS"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "WT"
            }
          }
        ]
      },
      "prior-hws-kf": {
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
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "HWS"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "KF"
            }
          }
        ]
      },
      "prior-hws-sag": {
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
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "HWS"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "sag"
            }
          }
        ]
      },
      "prior-hws-cor": {
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
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "HWS"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": ["cor", "kor"]
            }
          }
        ]
      }
    },
    "stages": [
      {
        "id": "ct-hws-prior-stage",
        "name": "HWS + VU",
        "viewportStructure": {
          "layoutType": "grid",
          "properties": {
            "rows": 2,
            "columns": 4
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
                "id": "hws-wt"
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
                "id": "hws-sag"
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
                "id": "hws-cor"
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
                "id": "hws-kf"
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
                "id": "prior-hws-wt"
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
                "id": "prior-hws-sag"
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
                "id": "prior-hws-cor"
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
                "id": "prior-hws-kf"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "ct-thorax-abdomen",
    "name": "CT Thorax/Abdomen",
    "locked": false,
    "isPreset": true,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "CT"
        },
        "required": true
      },
      {
        "attribute": "StudyDescription",
        "constraint": {
          "containsI": ["Thorax/Abdomen", "CTAB", "Thorax-Abdomen"]
        },
        "weight": 10
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "CTAB"
        },
        "weight": 10
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "doesNotContainI": "Wirbelsäule"
        },
        "required": true
      }
    ],
    "displaySetSelectors": {
      "ctab-nativ-ax": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "CTAB"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "NATIV"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "ax"
            }
          }
        ]
      },
      "ctab-ld-ax": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "CTAB"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "LD"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "ax"
            }
          }
        ]
      },
      "ctab-sag": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "CTAB"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "sag"
            }
          }
        ]
      },
      "ctab-cor": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "CTAB"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": ["cor", "kor"]
            }
          }
        ]
      }
    },
    "stages": [
      {
        "id": "ct-thorax-abdomen-stage",
        "name": "CTAB 2x2",
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
                "id": "ctab-nativ-ax"
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
                "id": "ctab-ld-ax"
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
                "id": "ctab-sag"
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
                "id": "ctab-cor"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "ct-thorax-abdomen-prior",
    "name": "CT Thorax/Abdomen mit VU",
    "locked": false,
    "isPreset": true,
    "numberOfPriorsReferenced": 1,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "CT"
        },
        "required": true
      },
      {
        "attribute": "StudyDescription",
        "constraint": {
          "containsI": ["Thorax/Abdomen", "CTAB", "Thorax-Abdomen"]
        },
        "weight": 10
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "CTAB"
        },
        "weight": 10
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "doesNotContainI": "Wirbelsäule"
        },
        "required": true
      }
    ],
    "displaySetSelectors": {
      "ctab-nativ-ax": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "CTAB"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "NATIV"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "ax"
            }
          }
        ]
      },
      "ctab-ld-ax": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "CTAB"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "LD"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "ax"
            }
          }
        ]
      },
      "ctab-sag": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "CTAB"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "sag"
            }
          }
        ]
      },
      "ctab-cor": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "CTAB"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": ["cor", "kor"]
            }
          }
        ]
      },
      "prior-ctab-nativ-ax": {
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
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "CTAB"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "NATIV"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "ax"
            }
          }
        ]
      },
      "prior-ctab-ld-ax": {
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
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "CTAB"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "LD"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "ax"
            }
          }
        ]
      },
      "prior-ctab-sag": {
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
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "CTAB"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "sag"
            }
          }
        ]
      },
      "prior-ctab-cor": {
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
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "CTAB"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": ["cor", "kor"]
            }
          }
        ]
      }
    },
    "stages": [
      {
        "id": "ct-thorax-abdomen-prior-stage",
        "name": "CTAB + VU",
        "viewportStructure": {
          "layoutType": "grid",
          "properties": {
            "rows": 2,
            "columns": 4
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
                "id": "ctab-nativ-ax"
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
                "id": "ctab-ld-ax"
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
                "id": "ctab-sag"
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
                "id": "ctab-cor"
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
                "id": "prior-ctab-nativ-ax"
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
                "id": "prior-ctab-ld-ax"
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
                "id": "prior-ctab-sag"
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
                "id": "prior-ctab-cor"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "ct-ctab-spine",
    "name": "CT Thorax/Abdomen + WS",
    "locked": false,
    "isPreset": true,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "CT"
        },
        "required": true
      },
      {
        "attribute": "StudyDescription",
        "constraint": {
          "containsI": ["Thorax/Abdomen", "CTAB", "Thorax-Abdomen"]
        },
        "weight": 10
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "CTAB"
        },
        "required": true
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "Wirbelsäule"
        },
        "weight": 15
      }
    ],
    "displaySetSelectors": {
      "ctab-ax": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "CTAB"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "NATIV"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "ax"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "doesNotContainI": "Wirbelsäule"
            }
          }
        ]
      },
      "ctab-spine-ax": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "CTAB"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "Wirbelsäule"
            }
          }
        ]
      },
      "ctab-sag": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "CTAB"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "sag"
            }
          }
        ]
      },
      "ctab-cor": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "CTAB"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": ["cor", "kor"]
            }
          }
        ]
      }
    },
    "stages": [
      {
        "id": "ct-ctab-spine-stage",
        "name": "CTAB + WS 2x2",
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
                "id": "ctab-ax"
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
                "id": "ctab-spine-ax"
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
                "id": "ctab-sag"
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
                "id": "ctab-cor"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "ct-ctab-spine-prior",
    "name": "CT Thorax/Abd + WS mit VU",
    "locked": false,
    "isPreset": true,
    "numberOfPriorsReferenced": 1,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "CT"
        },
        "required": true
      },
      {
        "attribute": "StudyDescription",
        "constraint": {
          "containsI": ["Thorax/Abdomen", "CTAB", "Thorax-Abdomen"]
        },
        "weight": 10
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "CTAB"
        },
        "required": true
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "Wirbelsäule"
        },
        "weight": 15
      }
    ],
    "displaySetSelectors": {
      "ctab-ax": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "CTAB"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "NATIV"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "ax"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "doesNotContainI": "Wirbelsäule"
            }
          }
        ]
      },
      "ctab-spine-ax": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "CTAB"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "Wirbelsäule"
            }
          }
        ]
      },
      "ctab-sag": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "CTAB"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "sag"
            }
          }
        ]
      },
      "ctab-cor": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "CTAB"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": ["cor", "kor"]
            }
          }
        ]
      },
      "prior-ctab-ax": {
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
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "CTAB"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "NATIV"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "ax"
            }
          }
        ]
      },
      "prior-ctab-spine-ax": {
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
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "CTAB"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "Wirbelsäule"
            }
          }
        ]
      },
      "prior-ctab-sag": {
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
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "CTAB"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "sag"
            }
          }
        ]
      },
      "prior-ctab-cor": {
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
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "CTAB"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": ["cor", "kor"]
            }
          }
        ]
      }
    },
    "stages": [
      {
        "id": "ct-ctab-spine-prior-stage",
        "name": "CTAB+WS + VU",
        "viewportStructure": {
          "layoutType": "grid",
          "properties": {
            "rows": 2,
            "columns": 4
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
                "id": "ctab-ax"
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
                "id": "ctab-spine-ax"
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
                "id": "ctab-sag"
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
                "id": "ctab-cor"
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
                "id": "prior-ctab-ax"
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
                "id": "prior-ctab-spine-ax"
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
                "id": "prior-ctab-sag"
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
                "id": "prior-ctab-cor"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "ct-mittelgesicht",
    "name": "CT Mittelgesicht",
    "locked": false,
    "isPreset": true,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "CT"
        },
        "required": true
      },
      {
        "attribute": "StudyDescription",
        "constraint": {
          "containsI": ["Mittelgesicht", "Mittelgesicht-MPR", " Gesicht"]
        },
        "weight": 10
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "Mittelgesicht"
        },
        "weight": 15
      }
    ],
    "displaySetSelectors": {
      "mg-ax": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "Mittelgesicht"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "MPR"
            }
          },
          {
            "attribute": "isReconstructable",
            "constraint": {
              "equals": true
            },
            "required": true
          }
        ]
      }
    },
    "stages": [
      {
        "id": "ct-mittelgesicht-stage",
        "name": "Mittelgesicht MPR",
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
              "viewportType": "volume",
              "orientation": "axial",
              "toolGroupId": "mpr"
            },
            "displaySets": [
              {
                "id": "mg-ax"
              }
            ]
          },
          {
            "viewportOptions": {
              "viewportType": "volume",
              "orientation": "sagittal",
              "toolGroupId": "mpr"
            },
            "displaySets": [
              {
                "id": "mg-ax"
              }
            ]
          },
          {
            "viewportOptions": {
              "viewportType": "volume",
              "orientation": "coronal",
              "toolGroupId": "mpr"
            },
            "displaySets": [
              {
                "id": "mg-ax"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "ct-mittelgesicht-prior",
    "name": "CT Mittelgesicht mit VU",
    "locked": false,
    "isPreset": true,
    "numberOfPriorsReferenced": 1,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "CT"
        },
        "required": true
      },
      {
        "attribute": "StudyDescription",
        "constraint": {
          "containsI": ["Mittelgesicht", "Mittelgesicht-MPR", " Gesicht"]
        },
        "weight": 10
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "Mittelgesicht"
        },
        "weight": 15
      }
    ],
    "displaySetSelectors": {
      "mg-ax": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "Mittelgesicht"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "MPR"
            }
          },
          {
            "attribute": "isReconstructable",
            "constraint": {
              "equals": true
            },
            "required": true
          }
        ]
      },
      "prior-mg-ax": {
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
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "Mittelgesicht"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "MPR"
            }
          },
          {
            "attribute": "isReconstructable",
            "constraint": {
              "equals": true
            },
            "required": true
          }
        ]
      }
    },
    "stages": [
      {
        "id": "ct-mittelgesicht-prior-stage",
        "name": "Mittelgesicht + VU",
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
              "viewportType": "volume",
              "orientation": "axial",
              "toolGroupId": "mpr"
            },
            "displaySets": [
              {
                "id": "mg-ax"
              }
            ]
          },
          {
            "viewportOptions": {
              "viewportType": "volume",
              "orientation": "sagittal",
              "toolGroupId": "mpr"
            },
            "displaySets": [
              {
                "id": "mg-ax"
              }
            ]
          },
          {
            "viewportOptions": {
              "viewportType": "volume",
              "orientation": "coronal",
              "toolGroupId": "mpr"
            },
            "displaySets": [
              {
                "id": "mg-ax"
              }
            ]
          },
          {
            "viewportOptions": {
              "viewportType": "volume",
              "orientation": "axial",
              "toolGroupId": "mpr"
            },
            "displaySets": [
              {
                "id": "prior-mg-ax"
              }
            ]
          },
          {
            "viewportOptions": {
              "viewportType": "volume",
              "orientation": "sagittal",
              "toolGroupId": "mpr"
            },
            "displaySets": [
              {
                "id": "prior-mg-ax"
              }
            ]
          },
          {
            "viewportOptions": {
              "viewportType": "volume",
              "orientation": "coronal",
              "toolGroupId": "mpr"
            },
            "displaySets": [
              {
                "id": "prior-mg-ax"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "ct-abdomen",
    "name": "CT Abdomen",
    "locked": false,
    "isPreset": true,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "CT"
        },
        "required": true
      },
      {
        "attribute": "StudyDescription",
        "constraint": {
          "containsI": ["Abdomen", "Abdomen/Becken"]
        },
        "weight": 10
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "Abdomen"
        },
        "weight": 10
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "doesNotContainI": "CTAB"
        },
        "required": true
      }
    ],
    "displaySetSelectors": {
      "abd-ax": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "Abdomen"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "ax"
            }
          },
          {
            "attribute": "isReconstructable",
            "constraint": {
              "equals": true
            },
            "required": true
          }
        ]
      }
    },
    "stages": [
      {
        "id": "ct-abdomen-stage",
        "name": "Abdomen MPR",
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
              "viewportType": "volume",
              "orientation": "axial",
              "toolGroupId": "mpr"
            },
            "displaySets": [
              {
                "id": "abd-ax"
              }
            ]
          },
          {
            "viewportOptions": {
              "viewportType": "volume",
              "orientation": "sagittal",
              "toolGroupId": "mpr"
            },
            "displaySets": [
              {
                "id": "abd-ax"
              }
            ]
          },
          {
            "viewportOptions": {
              "viewportType": "volume",
              "orientation": "coronal",
              "toolGroupId": "mpr"
            },
            "displaySets": [
              {
                "id": "abd-ax"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "ct-abdomen-prior",
    "name": "CT Abdomen mit VU",
    "locked": false,
    "isPreset": true,
    "numberOfPriorsReferenced": 1,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "CT"
        },
        "required": true
      },
      {
        "attribute": "StudyDescription",
        "constraint": {
          "containsI": ["Abdomen", "Abdomen/Becken"]
        },
        "weight": 10
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "Abdomen"
        },
        "weight": 10
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "doesNotContainI": "CTAB"
        },
        "required": true
      }
    ],
    "displaySetSelectors": {
      "abd-ax": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "Abdomen"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "ax"
            }
          },
          {
            "attribute": "isReconstructable",
            "constraint": {
              "equals": true
            },
            "required": true
          }
        ]
      },
      "prior-abd-ax": {
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
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "Abdomen"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "ax"
            }
          },
          {
            "attribute": "isReconstructable",
            "constraint": {
              "equals": true
            },
            "required": true
          }
        ]
      }
    },
    "stages": [
      {
        "id": "ct-abdomen-prior-stage",
        "name": "Abdomen + VU",
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
              "viewportType": "volume",
              "orientation": "axial",
              "toolGroupId": "mpr"
            },
            "displaySets": [
              {
                "id": "abd-ax"
              }
            ]
          },
          {
            "viewportOptions": {
              "viewportType": "volume",
              "orientation": "sagittal",
              "toolGroupId": "mpr"
            },
            "displaySets": [
              {
                "id": "abd-ax"
              }
            ]
          },
          {
            "viewportOptions": {
              "viewportType": "volume",
              "orientation": "coronal",
              "toolGroupId": "mpr"
            },
            "displaySets": [
              {
                "id": "abd-ax"
              }
            ]
          },
          {
            "viewportOptions": {
              "viewportType": "volume",
              "orientation": "axial",
              "toolGroupId": "mpr"
            },
            "displaySets": [
              {
                "id": "prior-abd-ax"
              }
            ]
          },
          {
            "viewportOptions": {
              "viewportType": "volume",
              "orientation": "sagittal",
              "toolGroupId": "mpr"
            },
            "displaySets": [
              {
                "id": "prior-abd-ax"
              }
            ]
          },
          {
            "viewportOptions": {
              "viewportType": "volume",
              "orientation": "coronal",
              "toolGroupId": "mpr"
            },
            "displaySets": [
              {
                "id": "prior-abd-ax"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "ct-osteo",
    "name": "CT Osteo (Extremitaeten)",
    "locked": false,
    "isPreset": true,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "CT"
        },
        "required": true
      },
      {
        "attribute": "StudyDescription",
        "constraint": {
          "containsI": ["Osteo", "OSG", "Knie", "Schulter", "Fuß", "Hand", "Oberschenkel", "Extremität", "Dental"]
        },
        "weight": 10
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": ["li.OS", "re.OS", "OSG", "Oberschenkel"]
        },
        "weight": 10
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "doesNotContainI": ["BBA", "CCT", "HWS", "CTAB"]
        },
        "required": true
      }
    ],
    "displaySetSelectors": {
      "re-os-cor": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "re."
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "OS"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": ["cor", "kor"]
            }
          }
        ]
      },
      "re-os-sag": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "re."
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "OS"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "sag"
            }
          }
        ]
      },
      "li-os-cor": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "li."
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "OS"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": ["cor", "kor"]
            }
          }
        ]
      },
      "li-os-sag": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "li."
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "OS"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "sag"
            }
          }
        ]
      }
    },
    "stages": [
      {
        "id": "ct-osteo-stage",
        "name": "Osteo bilateral",
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
                "id": "re-os-cor"
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
                "id": "li-os-cor"
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
                "id": "re-os-sag"
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
                "id": "li-os-sag"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "ct-osteo-prior",
    "name": "CT Osteo mit VU",
    "locked": false,
    "isPreset": true,
    "numberOfPriorsReferenced": 1,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "CT"
        },
        "required": true
      },
      {
        "attribute": "StudyDescription",
        "constraint": {
          "containsI": ["Osteo", "OSG", "Knie", "Schulter", "Fuß", "Hand", "Oberschenkel", "Extremität", "Dental"]
        },
        "weight": 10
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": ["li.OS", "re.OS", "OSG", "Oberschenkel"]
        },
        "weight": 10
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "doesNotContainI": ["BBA", "CCT", "HWS", "CTAB"]
        },
        "required": true
      }
    ],
    "displaySetSelectors": {
      "re-os-cor": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "re."
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "OS"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": ["cor", "kor"]
            }
          }
        ]
      },
      "li-os-cor": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "li."
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "OS"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": ["cor", "kor"]
            }
          }
        ]
      },
      "re-os-sag": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "re."
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "OS"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "sag"
            }
          }
        ]
      },
      "li-os-sag": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "li."
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "OS"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "sag"
            }
          }
        ]
      },
      "prior-re-os-cor": {
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
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "re."
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "OS"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": ["cor", "kor"]
            }
          }
        ]
      },
      "prior-li-os-cor": {
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
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "li."
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "OS"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": ["cor", "kor"]
            }
          }
        ]
      },
      "prior-re-os-sag": {
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
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "re."
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "OS"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "sag"
            }
          }
        ]
      },
      "prior-li-os-sag": {
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
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "li."
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "OS"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "sag"
            }
          }
        ]
      }
    },
    "stages": [
      {
        "id": "ct-osteo-prior-stage",
        "name": "Osteo + VU",
        "viewportStructure": {
          "layoutType": "grid",
          "properties": {
            "rows": 2,
            "columns": 4
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
                "id": "re-os-cor"
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
                "id": "li-os-cor"
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
                "id": "re-os-sag"
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
                "id": "li-os-sag"
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
                "id": "prior-re-os-cor"
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
                "id": "prior-li-os-cor"
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
                "id": "prior-re-os-sag"
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
                "id": "prior-li-os-sag"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "ct-polytrauma",
    "name": "CT Polytrauma",
    "locked": false,
    "isPreset": true,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "CT"
        },
        "required": true
      },
      {
        "attribute": "StudyDescription",
        "constraint": {
          "containsI": ["Polytrauma", "BBA", "Trauma"]
        },
        "weight": 10
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "BBA"
        },
        "weight": 15
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "OS"
        },
        "weight": 10
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "BBA"
        },
        "required": true
      }
    ],
    "displaySetSelectors": {
      "cct-wt": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "CCT"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "WT"
            }
          }
        ]
      },
      "cct-kf": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "CCT"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "KF"
            }
          }
        ]
      },
      "cct-sag": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "CCT"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "sag"
            }
          }
        ]
      },
      "hws-wt": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "HWS"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "WT"
            }
          }
        ]
      },
      "hws-sag": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "HWS"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "sag"
            }
          }
        ]
      },
      "hws-cor": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "HWS"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": ["cor", "kor"]
            }
          }
        ]
      },
      "bba-cor": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "BBA"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": ["cor", "kor"]
            }
          }
        ]
      },
      "os-cor": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "OS"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": ["cor", "kor"]
            }
          }
        ]
      },
      "us-cor": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "US"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": ["cor", "kor"]
            }
          }
        ]
      }
    },
    "stages": [
      {
        "id": "ct-polytrauma-stage",
        "name": "Polytrauma 3x3",
        "viewportStructure": {
          "layoutType": "grid",
          "properties": {
            "rows": 3,
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
                "id": "cct-wt"
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
                "id": "cct-kf"
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
                "id": "cct-sag"
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
                "id": "hws-wt"
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
                "id": "hws-sag"
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
                "id": "hws-cor"
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
                "id": "bba-cor"
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
                "id": "os-cor"
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
                "id": "us-cor"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "ct-polytrauma-prior",
    "name": "CT Polytrauma mit VU",
    "locked": false,
    "isPreset": true,
    "numberOfPriorsReferenced": 1,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "CT"
        },
        "required": true
      },
      {
        "attribute": "StudyDescription",
        "constraint": {
          "containsI": ["Polytrauma", "BBA", "Trauma"]
        },
        "weight": 10
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "BBA"
        },
        "weight": 15
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "OS"
        },
        "weight": 10
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "BBA"
        },
        "required": true
      }
    ],
    "displaySetSelectors": {
      "cct-wt": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "CCT"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "WT"
            }
          }
        ]
      },
      "cct-kf": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "CCT"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "KF"
            }
          }
        ]
      },
      "hws-wt": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "HWS"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "WT"
            }
          }
        ]
      },
      "bba-cor": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "BBA"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": ["cor", "kor"]
            }
          }
        ]
      },
      "prior-cct-wt": {
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
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "CCT"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "WT"
            }
          }
        ]
      },
      "prior-cct-kf": {
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
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "CCT"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "KF"
            }
          }
        ]
      },
      "prior-hws-wt": {
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
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "HWS"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "WT"
            }
          }
        ]
      },
      "prior-bba-cor": {
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
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "BBA"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": ["cor", "kor"]
            }
          }
        ]
      }
    },
    "stages": [
      {
        "id": "ct-polytrauma-prior-stage",
        "name": "Polytrauma + VU",
        "viewportStructure": {
          "layoutType": "grid",
          "properties": {
            "rows": 2,
            "columns": 4
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
                "id": "cct-wt"
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
                "id": "cct-kf"
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
                "id": "hws-wt"
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
                "id": "bba-cor"
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
                "id": "prior-cct-wt"
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
                "id": "prior-cct-kf"
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
                "id": "prior-hws-wt"
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
                "id": "prior-bba-cor"
              }
            ]
          }
        ]
      }
    ]
  }
];
