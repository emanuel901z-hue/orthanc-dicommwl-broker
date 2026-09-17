/**
 * lung-screening.js - Hanging Protocols fuer Lungen-CT-Screening
 *
 * Speziell fuer das organisierte Lungenkrebs-Screening (KBV KFE-RL):
 *   - lung-screening-axial: 1x1 axial, Lungen-Fenster (Standard)
 *   - lung-screening-mip: 1x1 MIP (Maximum Intensity Projection) fuer Rundherd-Detektion
 *   - lung-screening-prior: 2x1 fuer Voruntersuchungs-Vergleich (aktuell + Prior)
 *
 * Lung-RADS relevante Features:
 *   - Lungen-Fenster (W 1500, C -600) fuer Rundherd-Detektion
 *   - MIP fuer Detektion kleiner Rundherde (besonders Teil-solid)
 *   - Prior-Vergleich fuer Wachstumsbeurteilung (Kategorie-Upgrade)
 */
module.exports = [
  {
    "id": "lung-screening-axial",
    "name": "Lung Screening (Axial)",
    "locked": false,
    "isPreset": true,
    "protocolMatchingRules": [
      {
        "attribute": "Modalities",
        "constraint": {
          "contains": "CT"
        }
      },
      {
        "attribute": "StudyDescription",
        "constraint": {
          "contains": "LUNG"
        },
        "required": false
      }
    ],
    "displaySetSelectors": {
      "lung-ct-series": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            }
          }
        ]
      }
    },
    "stages": [
      {
        "id": "lung-axial-stage-1",
        "name": "Axial Lungen-Fenster",
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
              "viewportType": "stack"
            },
            "displaySets": [
              {
                "id": "lung-ct-series"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "lung-screening-mip",
    "name": "Lung Screening (MIP)",
    "locked": false,
    "isPreset": true,
    "protocolMatchingRules": [
      {
        "attribute": "Modalities",
        "constraint": {
          "contains": "CT"
        }
      }
    ],
    "displaySetSelectors": {
      "lung-ct-mip-series": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            }
          }
        ]
      }
    },
    "stages": [
      {
        "id": "lung-mip-stage-1",
        "name": "MIP Rundherd-Detektion",
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
              "viewportType": "volume"
            },
            "displaySets": [
              {
                "id": "lung-ct-mip-series"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "lung-screening-prior",
    "name": "Lung Screening (Prior-Vergleich)",
    "locked": false,
    "isPreset": true,
    "protocolMatchingRules": [
      {
        "attribute": "Modalities",
        "constraint": {
          "contains": "CT"
        }
      }
    ],
    "displaySetSelectors": {
      "lung-current-series": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            }
          },
          {
            "attribute": "isStaged",
            "constraint": {
              "equals": true
            },
            "required": false
          }
        ]
      },
      "lung-prior-series": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
            }
          },
          {
            "attribute": "isReferred",
            "constraint": {
              "equals": true
            },
            "required": false
          }
        ]
      }
    },
    "stages": [
      {
        "id": "lung-prior-stage-1",
        "name": "Aktuell vs Prior",
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
              "viewportType": "stack"
            },
            "displaySets": [
              {
                "id": "lung-current-series"
              }
            ]
          },
          {
            "viewportOptions": {
              "viewportType": "stack"
            },
            "displaySets": [
              {
                "id": "lung-prior-series"
              }
            ]
          }
        ]
      }
    ]
  }
];
