/**
 * ct-cranial.js - Hanging Protocols fuer OHIF v3
 * Automatisch extrahiert aus default.js.
 *
 * Protokolle (10):
 *   - ct-cct (CT Schaedel (CCT))
 *   - ct-cct-prior (CT Schaedel mit VU)
 *   - ct-cta (CTA Kopf-Hals)
 *   - ct-cta-prior (CTA Kopf-Hals mit VU)
 *   - ct-cta-head (CTA Hirnangiographie (Kopf-Hals))
 *   - ct-cta-head-prior (CTA Hirnangiographie mit VU)
 *   - ct-perfusion (CT Perfusion)
 *   - ct-cta-perfusion (CTA + Perfusion (Stroke))
 *   - ct-cta-perfusion-prior (CTA + Perfusion mit VU)
 *   - ct-hwt (CT Hirntod (HWT))
 */
module.exports = [
  {
    "id": "ct-cct",
    "name": "CT Schaedel (CCT)",
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
          "containsI": ["CCT", "CT-Kopf", "Spirale_nativ"]
        },
        "weight": 10
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "CCT"
        },
        "weight": 10
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "doesNotContainI": "CTA"
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
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "doesNotContainI": "KF"
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
      "cct-cor": {
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
              "containsI": ["cor", "kor"]
            }
          }
        ]
      }
    },
    "stages": [
      {
        "id": "ct-cct-stage",
        "name": "CCT 2x2",
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
                "id": "cct-cor"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "ct-cct-prior",
    "name": "CT Schaedel mit VU",
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
          "containsI": ["CCT", "CT-Kopf", "Spirale_nativ"]
        },
        "weight": 10
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "CCT"
        },
        "weight": 10
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "doesNotContainI": "CTA"
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
      }
    },
    "stages": [
      {
        "id": "ct-cct-prior-stage",
        "name": "CCT + VU",
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
          }
        ]
      }
    ]
  },
  {
    "id": "ct-cta",
    "name": "CTA Kopf-Hals",
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
          "containsI": ["CCT/CTA", "CTA"]
        },
        "weight": 15
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "CTA"
        },
        "weight": 10
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "doesNotContainI": "CTAB"
        },
        "required": true
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "doesNotContainI": "Kopf-Hals"
        },
        "required": true
      }
    ],
    "displaySetSelectors": {
      "cta-ax": {
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
              "containsI": "CTA"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "doesNotContainI": "CTAB"
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
      "cta-sag": {
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
              "containsI": "CTA"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "doesNotContainI": "CTAB"
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
      "cta-cor": {
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
              "containsI": "CTA"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "doesNotContainI": "CTAB"
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
      }
    },
    "stages": [
      {
        "id": "ct-cta-stage",
        "name": "CTA 2x2",
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
                "id": "cta-ax"
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
                "id": "cta-sag"
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
                "id": "cta-cor"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "ct-cta-prior",
    "name": "CTA Kopf-Hals mit VU",
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
          "containsI": ["CCT/CTA", "CTA"]
        },
        "weight": 15
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "CTA"
        },
        "weight": 10
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "doesNotContainI": "CTAB"
        },
        "required": true
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "doesNotContainI": "Kopf-Hals"
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
      "cta-ax": {
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
              "containsI": "CTA"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "doesNotContainI": "CTAB"
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
      "cta-sag": {
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
              "containsI": "CTA"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "doesNotContainI": "CTAB"
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
      "cta-cor": {
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
              "containsI": "CTA"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "doesNotContainI": "CTAB"
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
      "prior-cta-ax": {
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
              "containsI": "CTA"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "doesNotContainI": "CTAB"
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
      "prior-cta-sag": {
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
              "containsI": "CTA"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "doesNotContainI": "CTAB"
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
      "prior-cta-cor": {
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
              "containsI": "CTA"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "doesNotContainI": "CTAB"
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
        "id": "ct-cta-prior-stage",
        "name": "CTA + VU",
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
                "id": "cta-ax"
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
                "id": "cta-sag"
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
                "id": "cta-cor"
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
                "id": "prior-cta-ax"
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
                "id": "prior-cta-sag"
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
                "id": "prior-cta-cor"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "ct-cta-head",
    "name": "CTA Hirnangiographie (Kopf-Hals)",
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
          "containsI": ["Angio Kopf", "Kopf-Hals"]
        },
        "weight": 20
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "Kopf-Hals"
        },
        "weight": 30
      }
    ],
    "displaySetSelectors": {
      "cta-ax": {
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
              "containsI": "CTA"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "Kopf-Hals"
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
      "cta-sag": {
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
              "containsI": "CTA"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "Kopf-Hals"
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
      "cta-cor": {
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
              "containsI": "CTA"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "Kopf-Hals"
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
      }
    },
    "stages": [
      {
        "id": "ct-cta-head-stage",
        "name": "CTA Kopf-Hals 2x2",
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
                "id": "cta-ax"
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
                "id": "cta-sag"
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
                "id": "cta-cor"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "ct-cta-head-prior",
    "name": "CTA Hirnangiographie mit VU",
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
          "containsI": ["Angio Kopf", "Kopf-Hals"]
        },
        "weight": 20
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "Kopf-Hals"
        },
        "weight": 30
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
      "cta-ax": {
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
              "containsI": "CTA"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "Kopf-Hals"
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
      "cta-sag": {
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
              "containsI": "CTA"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "Kopf-Hals"
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
      "cta-cor": {
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
              "containsI": "CTA"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "Kopf-Hals"
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
      "prior-cta-ax": {
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
              "containsI": "CTA"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "Kopf-Hals"
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
      "prior-cta-sag": {
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
              "containsI": "CTA"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "Kopf-Hals"
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
      "prior-cta-cor": {
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
              "containsI": "CTA"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "Kopf-Hals"
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
        "id": "ct-cta-head-prior-stage",
        "name": "CTA Kopf-Hals + VU",
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
                "id": "cta-ax"
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
                "id": "cta-sag"
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
                "id": "cta-cor"
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
                "id": "prior-cta-ax"
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
                "id": "prior-cta-sag"
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
                "id": "prior-cta-cor"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "ct-perfusion",
    "name": "CT Perfusion",
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
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "Blood Flow"
        },
        "weight": 15
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
      "blood-flow": {
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
              "containsI": "Blood Flow"
            }
          }
        ]
      },
      "tmax": {
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
              "containsI": "TMax"
            }
          }
        ]
      },
      "blood-volume": {
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
              "containsI": "Blood Volume"
            }
          }
        ]
      }
    },
    "stages": [
      {
        "id": "ct-perfusion-stage",
        "name": "Perfusion 2x2",
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
                "id": "blood-flow"
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
                "id": "tmax"
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
                "id": "blood-volume"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "ct-cta-perfusion",
    "name": "CTA + Perfusion (Stroke)",
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
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "Blood Flow"
        },
        "weight": 15
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "CTA"
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
      "cta-ax": {
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
              "containsI": "CTA"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "doesNotContainI": "CTAB"
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
      "cta-sag": {
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
              "containsI": "CTA"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "doesNotContainI": "CTAB"
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
      "cta-cor": {
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
              "containsI": "CTA"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "doesNotContainI": "CTAB"
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
      "blood-flow": {
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
              "containsI": "Blood Flow"
            }
          }
        ]
      },
      "tmax": {
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
              "containsI": "TMax"
            }
          }
        ]
      },
      "blood-volume": {
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
              "containsI": "Blood Volume"
            }
          }
        ]
      },
      "mtt": {
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
              "containsI": "Mean Transit"
            }
          }
        ]
      },
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
      }
    },
    "stages": [
      {
        "id": "ct-cta-perfusion-stage",
        "name": "CTA+Perfusion 2x4",
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
                "id": "cta-ax"
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
                "id": "blood-flow"
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
                "id": "tmax"
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
                "id": "cta-sag"
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
                "id": "cta-cor"
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
                "id": "blood-volume"
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
                "id": "mtt"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "ct-cta-perfusion-prior",
    "name": "CTA + Perfusion mit VU",
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
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "Blood Flow"
        },
        "weight": 15
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "CTA"
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
      "cta-ax": {
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
              "containsI": "CTA"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "doesNotContainI": "CTAB"
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
      "blood-flow": {
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
              "containsI": "Blood Flow"
            }
          }
        ]
      },
      "tmax": {
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
              "containsI": "TMax"
            }
          }
        ]
      },
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
      "prior-cta-ax": {
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
              "containsI": "CTA"
            }
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "doesNotContainI": "CTAB"
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
      "prior-blood-flow": {
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
              "containsI": "Blood Flow"
            }
          }
        ]
      },
      "prior-tmax": {
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
              "containsI": "TMax"
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
      }
    },
    "stages": [
      {
        "id": "ct-cta-perfusion-prior-stage",
        "name": "CTA+Perfusion + VU",
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
                "id": "cta-ax"
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
                "id": "blood-flow"
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
                "id": "tmax"
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
                "id": "prior-cta-ax"
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
                "id": "prior-blood-flow"
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
                "id": "prior-tmax"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "ct-hwt",
    "name": "CT Hirntod (HWT)",
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
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "HWT"
        },
        "weight": 20
      }
    ],
    "displaySetSelectors": {
      "hwt-ax": {
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
              "containsI": "HWT"
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
      "hwt-cor": {
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
              "containsI": "HWT"
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
      "hwt-sag": {
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
              "containsI": "HWT"
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
        "id": "ct-hwt-stage",
        "name": "HWT 1x3",
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
                "id": "hwt-ax"
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
                "id": "hwt-cor"
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
                "id": "hwt-sag"
              }
            ]
          }
        ]
      }
    ]
  }
];
