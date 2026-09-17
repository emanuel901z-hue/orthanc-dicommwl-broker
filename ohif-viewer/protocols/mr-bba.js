/**
 * mr-bba.js - Hanging Protocols fuer MR Becken-Bein-Angio
 *
 * Protokolle (2):
 *   - mr-bba (MR Becken-Bein-Angio)
 *   - mr-bba-prior (MR Becken-Bein-Angio mit VU)
 *
 * Matching: StudyDescription containsI "BBA" (primaer, weight 30)
 *           seriesDescriptions containsI "Angio3D" (Siemens) / "mDIXON_MRA" (Philips)
 *
 * Vendor-Support:
 *   Siemens: I-IV_Angio3D_*_post_SUB, *_SUB_MIP_COR,
 *            MIP Angio, MIP Abdomen, MIP Oberschenkel, MIP Unterschenkel 1/2,
 *            t1_vibe_fs_tra_caipi3_bh_320_KM
 *   Philips: mDIXON_MRA_Pelvis/ULeg/LLeg,
 *            MIP tra 3D_mDIXON_MRA_Pelvis/ULeg/LLeg,
 *            MPR BBA TRA 3 mm_mDIXON_MRA_*,
 *            MobiView Radial MIP, MobiView T1W_mDIXON_FFE_TRA_spaet KM_BH
 *
 * Stage 1 "MIP Uebersicht": 2x3 Grid mit MIP-Serien pro Station + T1
 * Stage 2 "Subtraktion axial": 2x2 Grid mit 4 Stationen (SUB/mDIXON)
 *
 * Constraints: containsI (case-insensitive), arrays fuer Multi-Keyword-OR
 */
module.exports = [
  {
    "id": "mr-bba",
    "name": "MR Becken-Bein-Angio",
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
          "containsI": "BBA"
        },
        "weight": 30
      },
      {
        "attribute": "StudyDescription",
        "constraint": {
          "containsI": "Angio"
        },
        "weight": 15
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "Angio3D"
        },
        "weight": 20
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "mDIXON_MRA"
        },
        "weight": 20
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "MIP"
        },
        "weight": 10
      }
    ],
    "displaySetSelectors": {
      "mip-overview": {
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
              "containsI": ["MIP Angio", "Radial MIP"]
            },
            "required": true
          }
        ]
      },
      "mip-pelvis": {
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
              "containsI": ["MIP Abdomen", "MIP Pelvis", "MIP tra 3D_mDIXON_MRA_Pelvis"]
            },
            "required": true
          }
        ]
      },
      "mip-thigh": {
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
              "containsI": ["MIP Oberschenkel", "MIP ULeg", "MIP tra 3D_mDIXON_MRA_ULeg"]
            },
            "required": true
          }
        ]
      },
      "mip-calf1": {
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
              "containsI": ["MIP Unterschenkel 1", "MIP LLeg", "MIP tra 3D_mDIXON_MRA_LLeg"]
            },
            "required": true
          }
        ]
      },
      "mip-calf2": {
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
              "containsI": "MIP Unterschenkel 2"
            },
            "required": true
          }
        ]
      },
      "t1-native": {
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
              "containsI": ["vibe", "mDIXON_FFE"]
            },
            "required": true
          }
        ]
      },
      "sub-pelvis": {
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
              "containsI": ["abdomen", "Pelvis"]
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": ["SUB", "mDIXON_MRA"]
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "doesNotContain": "MIP"
            }
          }
        ]
      },
      "sub-thigh": {
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
              "containsI": ["upper_legs", "ULeg"]
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": ["SUB", "mDIXON_MRA"]
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "doesNotContain": "MIP"
            }
          }
        ]
      },
      "sub-calf": {
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
              "containsI": ["II_Angio3D_legs", "LLeg"]
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": ["SUB", "mDIXON_MRA"]
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "doesNotContain": "MIP"
            }
          }
        ]
      },
      "sub-feet": {
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
              "containsI": "feet"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "containsI": "SUB"
            },
            "required": true
          },
          {
            "attribute": "SeriesDescription",
            "constraint": {
              "doesNotContain": "MIP"
            }
          }
        ]
      }
    },
    "stages": [
      {
        "id": "mr-bba-mip-stage",
        "name": "MIP Uebersicht",
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
                "id": "mip-overview"
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
                "id": "mip-pelvis"
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
                "id": "mip-thigh"
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
                "id": "mip-calf1"
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
                "id": "mip-calf2"
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
                "id": "t1-native"
              }
            ]
          }
        ]
      },
      {
        "id": "mr-bba-sub-stage",
        "name": "Subtraktion axial",
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
                "id": "sub-pelvis"
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
                "id": "sub-thigh"
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
                "id": "sub-calf"
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
                "id": "sub-feet"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "mr-bba-prior",
    "name": "MR Becken-Bein-Angio mit VU",
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
          "containsI": "BBA"
        },
        "weight": 30
      },
      {
        "attribute": "StudyDescription",
        "constraint": {
          "containsI": "Angio"
        },
        "weight": 15
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "Angio3D"
        },
        "weight": 20
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "mDIXON_MRA"
        },
        "weight": 20
      },
      {
        "attribute": "seriesDescriptions",
        "constraint": {
          "containsI": "MIP"
        },
        "weight": 10
      }
    ],
    "displaySetSelectors": {
      "mip-overview": {
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
              "containsI": ["MIP Angio", "Radial MIP"]
            },
            "required": true
          }
        ]
      },
      "mip-pelvis": {
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
              "containsI": ["MIP Abdomen", "MIP Pelvis", "MIP tra 3D_mDIXON_MRA_Pelvis"]
            },
            "required": true
          }
        ]
      },
      "mip-thigh": {
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
              "containsI": ["MIP Oberschenkel", "MIP ULeg", "MIP tra 3D_mDIXON_MRA_ULeg"]
            },
            "required": true
          }
        ]
      },
      "prior-mip-overview": {
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
              "containsI": ["MIP Angio", "Radial MIP"]
            },
            "required": true
          }
        ]
      },
      "prior-mip-pelvis": {
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
              "containsI": ["MIP Abdomen", "MIP Pelvis", "MIP tra 3D_mDIXON_MRA_Pelvis"]
            },
            "required": true
          }
        ]
      },
      "prior-mip-thigh": {
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
              "containsI": ["MIP Oberschenkel", "MIP ULeg", "MIP tra 3D_mDIXON_MRA_ULeg"]
            },
            "required": true
          }
        ]
      }
    },
    "stages": [
      {
        "id": "mr-bba-prior-mip-stage",
        "name": "MIP Vergleich + VU",
        "viewportStructure": {
          "layoutType": "grid",
          "properties": {
            "rows": 3,
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
                "id": "mip-overview"
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
                "id": "prior-mip-overview"
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
                "id": "mip-pelvis"
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
                "id": "prior-mip-pelvis"
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
                "id": "mip-thigh"
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
                "id": "prior-mip-thigh"
              }
            ]
          }
        ]
      }
    ]
  }
];
