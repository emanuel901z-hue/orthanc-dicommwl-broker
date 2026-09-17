/**
 * mr-neuro.js - Hanging Protocols fuer MR Neurologie
 *
 * Protokolle (4):
 *   - mr-brain (MR Kopf/Schaedel: T2, FLAIR, DWI, T1+KM)
 *   - mr-brain-prior (MR Kopf/Schaedel mit VU)
 *   - mr-angio-head (MRA Kopf/Hals: TOF, MIP, T1+KM, Sub)
 *   - mr-angio-head-prior (MRA Kopf/Hals mit VU)
 *
 * Matching: StudyDescription containsI Kopf/Schaedel/NNH/Halsweichteil
 *           bzw. StudyDescription containsI MRA + seriesDescriptions TOF
 * Vendor-Support: Siemens (Incepto: t2_tse_sag_smbr, TOF_3D_multi-slab,
 *                 resolve_3scan_trace_tra, t1_se_fs_cor_3mm_KM)
 *                 Philips (PI FLAIR tra, 3D_TOF, DWI_b1000, T1W_FFE KM,
 *                 MIP_FH, MIP_RL, subtraktion, eMIP Carotis)
 *
 * Constraints: containsI (case-insensitive), arrays fuer Multi-Keyword-OR
 */
module.exports = [
  {
    "id": "mr-brain",
    "name": "MR Kopf",
    "locked": false,
    "isPreset": true,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "MR"
        },
        "required": true
      },
      {
        "attribute": "StudyDescription",
        "constraint": {
          "containsI": ["Kopf", "Schädel", "Schaedel", "NNH", "Halsweichteil"]
        },
        "weight": 20
      }
    ],
    "displaySetSelectors": {
      "t2-sag": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "MR"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "t2"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "sag"
            },
            "required": true
          }
        ]
      },
      "flair": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "MR"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": ["flair", "dark-fluid", "space"]
            },
            "required": true
          }
        ]
      },
      "dwi": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "MR"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": ["dwi", "trace", "adc"]
            },
            "required": true
          }
        ]
      },
      "t1-km": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "MR"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "t1"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": ["km", "contrast", "gad", "KM"]
            },
            "required": true
          }
        ]
      }
    },
    "stages": [
      {
        "id": "mr-brain-stage",
        "name": "Kopf 2x2",
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
                "id": "t2-sag"
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
                "id": "flair"
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
                "id": "dwi"
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
                "id": "t1-km"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "mr-brain-prior",
    "name": "MR Kopf mit VU",
    "locked": false,
    "isPreset": true,
    "numberOfPriorsReferenced": 1,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "MR"
        },
        "required": true
      },
      {
        "attribute": "StudyDescription",
        "constraint": {
          "containsI": ["Kopf", "Schädel", "Schaedel", "NNH", "Halsweichteil"]
        },
        "weight": 20
      }
    ],
    "displaySetSelectors": {
      "t2-sag": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "MR"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "t2"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "sag"
            },
            "required": true
          }
        ]
      },
      "flair": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "MR"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": ["flair", "dark-fluid", "space"]
            },
            "required": true
          }
        ]
      },
      "prior-t2-sag": {
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
              "equals": "MR"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "t2"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "sag"
            },
            "required": true
          }
        ]
      },
      "prior-flair": {
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
              "equals": "MR"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": ["flair", "dark-fluid", "space"]
            },
            "required": true
          }
        ]
      }
    },
    "stages": [
      {
        "id": "mr-brain-prior-stage",
        "name": "Kopf + VU",
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
                "id": "t2-sag"
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
                "id": "flair"
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
                "id": "prior-t2-sag"
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
                "id": "prior-flair"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "mr-angio-head",
    "name": "MRA Kopf/Hals",
    "locked": false,
    "isPreset": true,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "MR"
        },
        "required": true
      },
      {
        "attribute": "StudyDescription",
        "constraint": {
          "containsI": "MRA"
        },
        "weight": 25
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "TOF"
        },
        "weight": 20
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": ["subtraktion", "eMIP"]
        },
        "weight": 15
      }
    ],
    "displaySetSelectors": {
      "tof": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "MR"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "TOF"
            },
            "required": true
          }
        ]
      },
      "mip": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "MR"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "MIP"
            },
            "required": true
          }
        ]
      },
      "t1-km": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "MR"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "t1"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": ["km", "KM", "contrast", "gad"]
            },
            "required": true
          }
        ]
      },
      "sub": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "MR"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": ["subtraktion", "eMIP", "sub"]
            },
            "required": true
          }
        ]
      }
    },
    "stages": [
      {
        "id": "mr-angio-head-stage",
        "name": "MRA 2x2",
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
                "id": "tof"
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
                "id": "mip"
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
                "id": "t1-km"
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
                "id": "sub"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "mr-angio-head-prior",
    "name": "MRA Kopf/Hals mit VU",
    "locked": false,
    "isPreset": true,
    "numberOfPriorsReferenced": 1,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": "MR"
        },
        "required": true
      },
      {
        "attribute": "StudyDescription",
        "constraint": {
          "containsI": "MRA"
        },
        "weight": 25
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "TOF"
        },
        "weight": 20
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": ["subtraktion", "eMIP"]
        },
        "weight": 15
      }
    ],
    "displaySetSelectors": {
      "tof": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "MR"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "TOF"
            },
            "required": true
          }
        ]
      },
      "mip": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "MR"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "MIP"
            },
            "required": true
          }
        ]
      },
      "prior-tof": {
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
              "equals": "MR"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "TOF"
            },
            "required": true
          }
        ]
      },
      "prior-mip": {
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
              "equals": "MR"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "MIP"
            },
            "required": true
          }
        ]
      }
    },
    "stages": [
      {
        "id": "mr-angio-head-prior-stage",
        "name": "MRA + VU",
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
                "id": "tof"
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
                "id": "mip"
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
                "id": "prior-tof"
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
                "id": "prior-mip"
              }
            ]
          }
        ]
      }
    ]
  }
];
