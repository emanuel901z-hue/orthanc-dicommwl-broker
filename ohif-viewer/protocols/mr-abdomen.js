/**
 * mr-abdomen.js - Hanging Protocols fuer MR Abdomen/Becken
 *
 * Protokolle (2):
 *   - mr-abdomen (MR Abdomen/Oberbauch/Leber/MRCP/Nieren: T2, DWI, T1 dyn)
 *   - mr-prostate (MR Prostata/Becken: T2 triplan, DWI, T1)
 *
 * Matching: StudyDescription containsI Abdomen/Oberbauch/Leber/MRCP/Nieren/Pankreas
 *           bzw. Prostate/Prostata/Becken
 * Vendor-Support: Siemens (t2_haste_cor/tra, t1_fl2d_opp-in, ep2d_diff,
 *                 t1_vibe_fs_tra)
 *                 Philips (T2 SSH TSE cor/tra MS, T1W_mDIXON_nativ/Dynamik,
 *                 CS_DWI_B50_400_800, PI dual_FFE_BH)
 *
 * Constraints: containsI (case-insensitive), arrays fuer Multi-Keyword-OR
 */
module.exports = [
  {
    "id": "mr-abdomen",
    "name": "MR Abdomen",
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
          "containsI": ["Abdomen", "Oberbauch", "Leber", "MRCP", "Nieren", "Pankreas"]
        },
        "weight": 20
      }
    ],
    "displaySetSelectors": {
      "t2-cor": {
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
              "containsI": "cor"
            },
            "required": true
          }
        ]
      },
      "t2-tra": {
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
              "containsI": "tra"
            },
            "required": true
          }
        ]
      },
      "t1-dyn": {
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
              "containsI": ["t1", "dixon", "vibe", "fl2d", "dual_ffe", "mDIXON"]
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
              "containsI": ["dwi", "diff", "tracew", "adc"]
            },
            "required": true
          }
        ]
      }
    },
    "stages": [
      {
        "id": "mr-abdomen-stage",
        "name": "Abdomen 2x2",
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
                "id": "t2-cor"
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
                "id": "t2-tra"
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
                "id": "t1-dyn"
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
          }
        ]
      }
    ]
  },
  {
    "id": "mr-prostate",
    "name": "MR Prostata",
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
          "containsI": ["Prostate", "Prostata", "Becken"]
        },
        "weight": 25
      }
    ],
    "displaySetSelectors": {
      "t2-tra": {
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
              "containsI": "tra"
            },
            "required": true
          }
        ]
      },
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
      "t2-cor": {
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
              "containsI": "cor"
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
              "containsI": ["dwi", "diff", "tracew", "adc"]
            },
            "required": true
          }
        ]
      },
      "t1-tra": {
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
              "containsI": "tra"
            },
            "required": true
          }
        ]
      },
      "adc": {
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
              "containsI": "ADC"
            },
            "required": true
          }
        ]
      }
    },
    "stages": [
      {
        "id": "mr-prostate-stage",
        "name": "Prostata 2x3",
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
                "id": "t2-tra"
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
                "id": "t2-cor"
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
                "id": "adc"
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
                "id": "t1-tra"
              }
            ]
          }
        ]
      }
    ]
  }
];
