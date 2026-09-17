/**
 * mr-msk.js - Hanging Protocols fuer MR Musculoskeletal (MSK)
 *
 * Protokolle (2):
 *   - mr-knee (MR Knie: PD fs sag/cor/tra, T1 sag)
 *   - mr-shoulder (MR Schulter: PD fs tra/cor/sag, T1 cor)
 *
 * Matching: StudyDescription containsI Knie / Schulter
 * Vendor-Support: Siemens (Knie Dot Engine: pd_tse_fs_sag/tra/cor, t1_tse_sag)
 *                 Philips (PI PD SPIR sag/tra/cor, PI T1 sag, PI T2 VKB)
 *                 Siemens (Schulter: pd_tse_fs_tra/cor/sag, t1_tse_cor,
 *                          t1_tse_cor_fs_KM, t1_tse_tra_fs_KM)
 *
 * Constraints: containsI (case-insensitive), arrays fuer Multi-Keyword-OR
 */
module.exports = [
  {
    "id": "mr-knee",
    "name": "MR Knie",
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
          "containsI": "Knie"
        },
        "weight": 20
      }
    ],
    "displaySetSelectors": {
      "pd-sag": {
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
              "containsI": ["pd", "spir"]
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
      "pd-cor": {
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
              "containsI": ["pd", "spir"]
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
      "pd-tra": {
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
              "containsI": ["pd", "spir"]
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
      "t1-sag": {
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
              "containsI": "sag"
            },
            "required": true
          }
        ]
      }
    },
    "stages": [
      {
        "id": "mr-knee-stage",
        "name": "Knie 2x2",
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
                "id": "pd-sag"
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
                "id": "pd-cor"
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
                "id": "pd-tra"
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
                "id": "t1-sag"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "mr-shoulder",
    "name": "MR Schulter",
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
          "containsI": "Schulter"
        },
        "weight": 20
      }
    ],
    "displaySetSelectors": {
      "pd-tra": {
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
              "containsI": ["pd", "spir"]
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
      "t1-cor": {
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
              "containsI": "cor"
            },
            "required": true
          }
        ]
      },
      "pd-cor": {
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
              "containsI": ["pd", "spir"]
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
      "pd-sag": {
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
              "containsI": ["pd", "spir"]
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
      }
    },
    "stages": [
      {
        "id": "mr-shoulder-stage",
        "name": "Schulter 2x2",
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
                "id": "pd-tra"
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
                "id": "t1-cor"
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
                "id": "pd-cor"
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
                "id": "pd-sag"
              }
            ]
          }
        ]
      }
    ]
  }
];
