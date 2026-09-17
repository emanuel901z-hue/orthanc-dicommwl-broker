/**
 * generic.js - Hanging Protocols fuer OHIF v3
 * Automatisch extrahiert aus default.js.
 *
 * Protokolle (8):
 *   - ct-default (CT Default)
 *   - ct-mpr (CT MPR)
 *   - ct-mip (CT MIP/MinIP/Avg)
 *   - ct-mpr-mip (CT MPR + MIP)
 *   - mr-default (MR Default)
 *   - mr-mpr (MR MPR)
 *   - dx-default (Roentgen Default)
 *   - ptct-fusion (PET/CT Fusion)
 */
module.exports = [
  {
    "id": "ct-default",
    "name": "CT Default",
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
      "ct-default-series": {
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
        "id": "ct-stage-1",
        "name": "CT Stage 1",
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
                "id": "ct-default-series"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "ct-mpr",
    "name": "CT MPR",
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
      "ct-series": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
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
        "id": "ct-mpr-stage",
        "name": "CT MPR",
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
                "id": "ct-series"
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
                "id": "ct-series"
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
                "id": "ct-series"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "ct-mip",
    "name": "CT MIP/MinIP/Avg",
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
      "ct-series": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
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
        "id": "ct-mip-stage",
        "name": "CT MIP/MinIP/Avg",
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
                "id": "ct-series",
                "options": {
                  "blendMode": "mip",
                  "slabThickness": "fullVolume"
                }
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
                "id": "ct-series",
                "options": {
                  "blendMode": "minip",
                  "slabThickness": "fullVolume"
                }
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
                "id": "ct-series",
                "options": {
                  "blendMode": "avg",
                  "slabThickness": "fullVolume"
                }
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "ct-mpr-mip",
    "name": "CT MPR + MIP",
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
      "ct-series": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "CT"
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
        "id": "ct-mpr-mip-stage",
        "name": "CT MPR + MIP",
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
              "viewportType": "volume",
              "orientation": "axial",
              "toolGroupId": "mpr"
            },
            "displaySets": [
              {
                "id": "ct-series"
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
                "id": "ct-series"
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
                "id": "ct-series"
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
                "id": "ct-series",
                "options": {
                  "blendMode": "mip",
                  "slabThickness": "fullVolume"
                }
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "mr-default",
    "name": "MR Default",
    "locked": false,
    "isPreset": true,
    "protocolMatchingRules": [
      {
        "attribute": "Modalities",
        "constraint": {
          "contains": "MR"
        }
      }
    ],
    "displaySetSelectors": {
      "mr-series": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "MR"
            }
          }
        ]
      }
    },
    "stages": [
      {
        "id": "mr-stage-1",
        "name": "MR Stage 1",
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
              "viewportType": "stack"
            },
            "displaySets": [
              {
                "id": "mr-series",
                "displaySetIndex": 0
              }
            ]
          },
          {
            "viewportOptions": {
              "viewportType": "stack"
            },
            "displaySets": [
              {
                "id": "mr-series",
                "displaySetIndex": 1
              }
            ]
          },
          {
            "viewportOptions": {
              "viewportType": "stack"
            },
            "displaySets": [
              {
                "id": "mr-series",
                "displaySetIndex": 2
              }
            ]
          },
          {
            "viewportOptions": {
              "viewportType": "stack"
            },
            "displaySets": [
              {
                "id": "mr-series",
                "displaySetIndex": 3
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "mr-mpr",
    "name": "MR MPR",
    "locked": false,
    "isPreset": true,
    "protocolMatchingRules": [
      {
        "attribute": "Modalities",
        "constraint": {
          "contains": "MR"
        }
      }
    ],
    "displaySetSelectors": {
      "mr-series": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "MR"
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
        "id": "mr-mpr-stage",
        "name": "MR MPR",
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
                "id": "mr-series"
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
                "id": "mr-series"
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
                "id": "mr-series"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "dx-default",
    "name": "Roentgen Default",
    "locked": false,
    "isPreset": true,
    "protocolMatchingRules": [
      {
        "attribute": "Modalities",
        "constraint": {
          "contains": "DX"
        }
      }
    ],
    "displaySetSelectors": {
      "dx-series": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "DX"
            }
          }
        ]
      }
    },
    "stages": [
      {
        "id": "dx-stage-1",
        "name": "DX Stage 1",
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
                "id": "dx-series"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "ptct-fusion",
    "name": "PET/CT Fusion",
    "locked": false,
    "isPreset": true,
    "protocolMatchingRules": [
      {
        "attribute": "ModalitiesInStudy",
        "constraint": {
          "contains": [
            "CT",
            "PT"
          ]
        }
      }
    ],
    "displaySetSelectors": {
      "ctDisplaySet": {
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
          }
        ]
      },
      "ptDisplaySet": {
        "seriesMatchingRules": [
          {
            "attribute": "Modality",
            "constraint": {
              "equals": "PT"
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
            "attribute": "sameAs",
            "sameAttribute": "FrameOfReferenceUID",
            "sameDisplaySetId": "ctDisplaySet",
            "constraint": {
              "equals": {
                "value": true
              }
            }
          }
        ]
      }
    },
    "stages": [
      {
        "id": "ptct-stage",
        "name": "PET/CT",
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
              "viewportType": "volume",
              "orientation": "axial",
              "toolGroupId": "ptct"
            },
            "displaySets": [
              {
                "id": "ctDisplaySet"
              }
            ]
          },
          {
            "viewportOptions": {
              "viewportType": "volume",
              "orientation": "axial",
              "toolGroupId": "ptct"
            },
            "displaySets": [
              {
                "id": "ptDisplaySet",
                "options": {
                  "colormap": {
                    "name": "hsv"
                  }
                }
              }
            ]
          },
          {
            "viewportOptions": {
              "viewportType": "volume",
              "orientation": "axial",
              "toolGroupId": "ptct"
            },
            "displaySets": [
              {
                "id": "ctDisplaySet"
              },
              {
                "id": "ptDisplaySet",
                "options": {
                  "colormap": {
                    "name": "hsv",
                    "opacity": 0.7
                  }
                }
              }
            ]
          },
          {
            "viewportOptions": {
              "viewportType": "volume",
              "orientation": "coronal",
              "toolGroupId": "ptct"
            },
            "displaySets": [
              {
                "id": "ptDisplaySet",
                "options": {
                  "blendMode": "mip",
                  "slabThickness": "fullVolume"
                }
              }
            ]
          }
        ]
      }
    ]
  }
];
