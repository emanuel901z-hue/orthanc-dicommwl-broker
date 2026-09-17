/**
 * ct-angio.js - Hanging Protocols fuer OHIF v3
 * CT-Angiographie Protokolle, optimiert fuer PACS-Realitaet.
 *
 * Protokolle (4):
 *   - ct-bba (CT Becken-Bein-Angio (BBA))
 *   - ct-bba-prior (CT Becken-Bein-Angio mit VU)
 *   - ct-cta-aorta (CT-Angio Aorta)
 *   - ct-cta-aorta-prior (CT-Angio Aorta mit VU)
 */
module.exports = [
  {
    "id": "ct-bba",
    "name": "CT Becken-Bein-Angio (BBA)",
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
          "containsI": "BBA"
        },
        "weight": 20
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "BBA"
        },
        "weight": 20
      }
    ],
    "displaySetSelectors": {
      "bba-ax": {
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
      "bba-sag": {
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
              "containsI": "sag"
            }
          }
        ]
      }
    },
    "stages": [
      {
        "id": "ct-bba-stage",
        "name": "BBA ax+cor+sag",
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
                "id": "bba-ax"
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
                "id": "bba-sag"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "ct-bba-prior",
    "name": "CT Becken-Bein-Angio mit VU",
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
          "containsI": "BBA"
        },
        "weight": 20
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "BBA"
        },
        "weight": 20
      }
    ],
    "displaySetSelectors": {
      "bba-ax": {
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
      "bba-sag": {
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
              "containsI": "sag"
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
      },
      "prior-bba-ax": {
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
      "prior-bba-sag": {
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
              "containsI": "sag"
            }
          }
        ]
      }
    },
    "stages": [
      {
        "id": "ct-bba-prior-stage",
        "name": "BBA + VU",
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
                "id": "bba-ax"
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
                "id": "bba-sag"
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
                "id": "prior-bba-ax"
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
          },
          {
            "viewportOptions": {
              "viewportType": "stack",
              "toolGroupId": "default"
            },
            "displaySets": [
              {
                "id": "prior-bba-sag"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "ct-cta-aorta",
    "name": "CT-Angio Aorta",
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
          "containsI": "Aorta"
        },
        "weight": 20
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "Aorta"
        },
        "weight": 15
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "doesNotContainI": "BBA"
        },
        "required": true
      }
    ],
    "displaySetSelectors": {
      "aorta-ax": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "isReconstructable",
            "constraint": {
              "equals": true
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "Aorta"
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
      "aorta-sag": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "isReconstructable",
            "constraint": {
              "equals": true
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "Aorta"
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
      "aorta-cor": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "isReconstructable",
            "constraint": {
              "equals": true
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "Aorta"
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
        "id": "ct-cta-aorta-stage",
        "name": "Aorta MPR 1x3",
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
                "id": "aorta-ax"
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
                "id": "aorta-sag"
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
                "id": "aorta-cor"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "ct-cta-aorta-prior",
    "name": "CT-Angio Aorta mit VU",
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
          "containsI": "Aorta"
        },
        "weight": 20
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "Aorta"
        },
        "weight": 15
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "doesNotContainI": "BBA"
        },
        "required": true
      }
    ],
    "displaySetSelectors": {
      "aorta-ax": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "isReconstructable",
            "constraint": {
              "equals": true
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "Aorta"
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
      "aorta-sag": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "isReconstructable",
            "constraint": {
              "equals": true
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "Aorta"
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
      "aorta-cor": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            },
            "required": true
          },
          {
            "attribute": "isReconstructable",
            "constraint": {
              "equals": true
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "Aorta"
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
      "prior-aorta-ax": {
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
            "attribute": "isReconstructable",
            "constraint": {
              "equals": true
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "Aorta"
            }
          }
        ]
      }
    },
    "stages": [
      {
        "id": "ct-cta-aorta-prior-stage",
        "name": "Aorta + VU 2x3",
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
                "id": "aorta-ax"
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
                "id": "aorta-sag"
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
                "id": "aorta-cor"
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
                "id": "prior-aorta-ax"
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
                "id": "prior-aorta-ax"
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
                "id": "prior-aorta-ax"
              }
            ]
          }
        ]
      }
    ]
  }
];
