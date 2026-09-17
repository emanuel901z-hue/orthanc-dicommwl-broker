// ============================================================================
// OHIF v3 App-Konfiguration (default.js)
// ============================================================================
// Diese Datei wurde automatisch von build-config.js assembliert.
// NICHT MANUELL BEARBETEN - Aenderungen an den Modulen in protocols/ bzw.
// an static-config.js vornehmen und build-config.js neu ausfuehren.
//
// Module:
//   - generic.js (8 Protokolle)
//   - ct-cranial.js (10 Protokolle)
//   - ct-angio.js (4 Protokolle)
//   - ct-body-trauma.js (14 Protokolle)
//   - dx-skeleton.js (9 Protokolle)
//   - dx-extremity.js (16 Protokolle)
//   - mr.js (2 Protokolle)
//   - mr-neuro.js (4 Protokolle)
//   - mr-msk.js (2 Protokolle)
//   - mr-abdomen.js (2 Protokolle)
//   - mr-bba.js (2 Protokolle)
//   - xa-dsa.js (7 Protokolle)
// Gesamt: 80 Hanging Protocols
// ============================================================================

window.config = {
  "routerBasename": "/",
  "showStudyList": true,
  "showLoadingIndicator": true,
  "studyListFunctionsEnabled": true,
  "defaultDataSourceName": "dicomweb",
  "showPatientInfo": "visibleReadOnly",
  "studyPrefetcher": {
    "enabled": true,
    "displaySetsCount": 2,
    "maxNumPrefetchRequests": 10,
    "order": "closest"
  },
  "maxNumRequests": {
    "interaction": 100,
    "thumbnail": 75,
    "prefetch": 25
  },
  "extensions": [],
  "modes": [],
  "investigationalUseDialog": {
    "option": "never"
  },
  "dataSources": [
    {
      "namespace": "@ohif/extension-default.dataSourcesModule.dicomweb",
      "sourceName": "dicomweb",
      "configuration": {
        "friendlyName": "Carestream PACS (DICOMweb)",
        "name": "dicomweb",
        "qidoRoot": "/qido",
        "wadoRoot": "/wado",
        "wadoUriRoot": "/wadouri",
        "qidoSupportsIncludeField": true,
        "qidoSupportsFuzzyMatching": false,
        "supportsFuzzyMatching": false,
        "imageRendering": "wadors",
        "thumbnailRendering": "wadors",
        "studyInstanceUid": true,
        "seriesInstanceUid": true,
        "sopInstanceUid": true,
        "enableStudyLazyLoad": true,
        "supportsReject": false,
        "omitQuotationForMultipartRequest": true,
        "staticWado": false,
        "queryLimit": 100,
        "requestOptions": {
          "headers": {}
        }
      }
    }
  ],
  "hangingProtocols": [
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
    },
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
            "containsI": [
              "CCT",
              "CT-Kopf",
              "Spirale_nativ"
            ]
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
                "containsI": [
                  "cor",
                  "kor"
                ]
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
            "containsI": [
              "CCT",
              "CT-Kopf",
              "Spirale_nativ"
            ]
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
            "containsI": [
              "CCT/CTA",
              "CTA"
            ]
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
                "containsI": [
                  "cor",
                  "kor"
                ]
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
            "containsI": [
              "CCT/CTA",
              "CTA"
            ]
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
                "containsI": [
                  "cor",
                  "kor"
                ]
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
                "containsI": [
                  "cor",
                  "kor"
                ]
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
            "containsI": [
              "Angio Kopf",
              "Kopf-Hals"
            ]
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
                "containsI": [
                  "cor",
                  "kor"
                ]
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
            "containsI": [
              "Angio Kopf",
              "Kopf-Hals"
            ]
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
                "containsI": [
                  "cor",
                  "kor"
                ]
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
                "containsI": [
                  "cor",
                  "kor"
                ]
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
                "containsI": [
                  "cor",
                  "kor"
                ]
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
                "containsI": [
                  "cor",
                  "kor"
                ]
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
    },
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
                "containsI": [
                  "cor",
                  "kor"
                ]
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
                "containsI": [
                  "cor",
                  "kor"
                ]
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
                "containsI": [
                  "cor",
                  "kor"
                ]
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
                "containsI": [
                  "cor",
                  "kor"
                ]
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
                "containsI": [
                  "cor",
                  "kor"
                ]
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
    },
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
                "containsI": [
                  "cor",
                  "kor"
                ]
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
                "containsI": [
                  "cor",
                  "kor"
                ]
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
                "containsI": [
                  "cor",
                  "kor"
                ]
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
            "containsI": [
              "Thorax/Abdomen",
              "CTAB",
              "Thorax-Abdomen"
            ]
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
                "containsI": [
                  "cor",
                  "kor"
                ]
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
            "containsI": [
              "Thorax/Abdomen",
              "CTAB",
              "Thorax-Abdomen"
            ]
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
                "containsI": [
                  "cor",
                  "kor"
                ]
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
                "containsI": [
                  "cor",
                  "kor"
                ]
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
            "containsI": [
              "Thorax/Abdomen",
              "CTAB",
              "Thorax-Abdomen"
            ]
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
                "containsI": [
                  "cor",
                  "kor"
                ]
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
            "containsI": [
              "Thorax/Abdomen",
              "CTAB",
              "Thorax-Abdomen"
            ]
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
                "containsI": [
                  "cor",
                  "kor"
                ]
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
                "containsI": [
                  "cor",
                  "kor"
                ]
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
            "containsI": [
              "Mittelgesicht",
              "Mittelgesicht-MPR",
              " Gesicht"
            ]
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
            "containsI": [
              "Mittelgesicht",
              "Mittelgesicht-MPR",
              " Gesicht"
            ]
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
            "containsI": [
              "Abdomen",
              "Abdomen/Becken"
            ]
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
            "containsI": [
              "Abdomen",
              "Abdomen/Becken"
            ]
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
            "containsI": [
              "Osteo",
              "OSG",
              "Knie",
              "Schulter",
              "Fuß",
              "Hand",
              "Oberschenkel",
              "Extremität",
              "Dental"
            ]
          },
          "weight": 10
        },
        {
          "attribute": "seriesDescriptions",
          "constraint": {
            "containsI": [
              "li.OS",
              "re.OS",
              "OSG",
              "Oberschenkel"
            ]
          },
          "weight": 10
        },
        {
          "attribute": "seriesDescriptions",
          "constraint": {
            "doesNotContainI": [
              "BBA",
              "CCT",
              "HWS",
              "CTAB"
            ]
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
                "containsI": [
                  "cor",
                  "kor"
                ]
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
                "containsI": [
                  "cor",
                  "kor"
                ]
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
            "containsI": [
              "Osteo",
              "OSG",
              "Knie",
              "Schulter",
              "Fuß",
              "Hand",
              "Oberschenkel",
              "Extremität",
              "Dental"
            ]
          },
          "weight": 10
        },
        {
          "attribute": "seriesDescriptions",
          "constraint": {
            "containsI": [
              "li.OS",
              "re.OS",
              "OSG",
              "Oberschenkel"
            ]
          },
          "weight": 10
        },
        {
          "attribute": "seriesDescriptions",
          "constraint": {
            "doesNotContainI": [
              "BBA",
              "CCT",
              "HWS",
              "CTAB"
            ]
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
                "containsI": [
                  "cor",
                  "kor"
                ]
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
                "containsI": [
                  "cor",
                  "kor"
                ]
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
                "containsI": [
                  "cor",
                  "kor"
                ]
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
                "containsI": [
                  "cor",
                  "kor"
                ]
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
            "containsI": [
              "Polytrauma",
              "BBA",
              "Trauma"
            ]
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
                "containsI": [
                  "cor",
                  "kor"
                ]
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
                "containsI": [
                  "cor",
                  "kor"
                ]
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
                "containsI": [
                  "cor",
                  "kor"
                ]
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
                "containsI": [
                  "cor",
                  "kor"
                ]
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
            "containsI": [
              "Polytrauma",
              "BBA",
              "Trauma"
            ]
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
                "containsI": [
                  "cor",
                  "kor"
                ]
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
                "containsI": [
                  "cor",
                  "kor"
                ]
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
    },
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
    },
    {
      "id": "dx-elbow",
      "name": "Roentgen Ellenbogen",
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
            "contains": "Ellenbogen"
          },
          "weight": 15
        }
      ],
      "displaySetSelectors": {
        "elbow-vd": {
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
                "contains": "Ellenbogen"
              }
            },
            {
              "attribute": "SeriesDescription",
              "constraint": {
                "contains": "VD"
              }
            }
          ]
        },
        "elbow-lat": {
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
                "contains": "Ellenbogen"
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
          "id": "dx-elbow-stage",
          "name": "Ellenbogen VD+LAT",
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
                  "id": "elbow-vd"
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
                  "id": "elbow-lat"
                }
              ]
            }
          ]
        }
      ]
    },
    {
      "id": "dx-elbow-prior",
      "name": "Roentgen Ellenbogen mit VU",
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
            "contains": "Ellenbogen"
          },
          "weight": 15
        }
      ],
      "displaySetSelectors": {
        "elbow-vd": {
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
                "contains": "Ellenbogen"
              }
            },
            {
              "attribute": "SeriesDescription",
              "constraint": {
                "contains": "VD"
              }
            }
          ]
        },
        "elbow-lat": {
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
                "contains": "Ellenbogen"
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
        "prior-elbow-vd": {
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
                "contains": "Ellenbogen"
              }
            },
            {
              "attribute": "SeriesDescription",
              "constraint": {
                "contains": "VD"
              }
            }
          ]
        },
        "prior-elbow-lat": {
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
                "contains": "Ellenbogen"
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
          "id": "dx-elbow-prior-stage",
          "name": "Ellenbogen + VU",
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
                  "id": "elbow-vd"
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
                  "id": "elbow-lat"
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
                  "id": "prior-elbow-vd"
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
                  "id": "prior-elbow-lat"
                }
              ]
            }
          ]
        }
      ]
    },
    {
      "id": "dx-wrist",
      "name": "Roentgen Handgelenk",
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
            "contains": "Handgelenk"
          },
          "weight": 15
        }
      ],
      "displaySetSelectors": {
        "wrist-dv": {
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
                "contains": "Handgelenk"
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
        "wrist-lat": {
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
                "contains": "Handgelenk"
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
          "id": "dx-wrist-stage",
          "name": "Handgelenk DV+LAT",
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
                  "id": "wrist-dv"
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
                  "id": "wrist-lat"
                }
              ]
            }
          ]
        }
      ]
    },
    {
      "id": "dx-wrist-prior",
      "name": "Roentgen Handgelenk mit VU",
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
            "contains": "Handgelenk"
          },
          "weight": 15
        }
      ],
      "displaySetSelectors": {
        "wrist-dv": {
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
                "contains": "Handgelenk"
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
        "wrist-lat": {
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
                "contains": "Handgelenk"
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
        "prior-wrist-dv": {
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
                "contains": "Handgelenk"
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
        "prior-wrist-lat": {
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
                "contains": "Handgelenk"
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
          "id": "dx-wrist-prior-stage",
          "name": "Handgelenk + VU",
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
                  "id": "wrist-dv"
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
                  "id": "wrist-lat"
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
                  "id": "prior-wrist-dv"
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
                  "id": "prior-wrist-lat"
                }
              ]
            }
          ]
        }
      ]
    },
    {
      "id": "dx-knee",
      "name": "Roentgen Kniegelenk",
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
            "contains": "Knie"
          },
          "weight": 15
        }
      ],
      "displaySetSelectors": {
        "knee-ap": {
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
                "contains": "Knie"
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
        "knee-lat": {
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
                "contains": "Knie"
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
          "id": "dx-knee-stage",
          "name": "Knie AP+LAT",
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
                  "id": "knee-ap"
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
                  "id": "knee-lat"
                }
              ]
            }
          ]
        }
      ]
    },
    {
      "id": "dx-knee-prior",
      "name": "Roentgen Kniegelenk mit VU",
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
            "contains": "Knie"
          },
          "weight": 15
        }
      ],
      "displaySetSelectors": {
        "knee-ap": {
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
                "contains": "Knie"
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
        "knee-lat": {
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
                "contains": "Knie"
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
        "prior-knee-ap": {
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
                "contains": "Knie"
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
        "prior-knee-lat": {
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
                "contains": "Knie"
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
          "id": "dx-knee-prior-stage",
          "name": "Knie + VU",
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
                  "id": "knee-ap"
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
                  "id": "knee-lat"
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
                  "id": "prior-knee-ap"
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
                  "id": "prior-knee-lat"
                }
              ]
            }
          ]
        }
      ]
    },
    {
      "id": "dx-ankle",
      "name": "Roentgen Sprunggelenk",
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
            "contains": "Sprunggelenk"
          },
          "weight": 15
        }
      ],
      "displaySetSelectors": {
        "ankle-ap": {
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
                "contains": "Sprunggelenk"
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
        "ankle-lat": {
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
                "contains": "Sprunggelenk"
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
          "id": "dx-ankle-stage",
          "name": "Sprunggelenk AP+LAT",
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
                  "id": "ankle-ap"
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
                  "id": "ankle-lat"
                }
              ]
            }
          ]
        }
      ]
    },
    {
      "id": "dx-ankle-prior",
      "name": "Roentgen Sprunggelenk mit VU",
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
            "contains": "Sprunggelenk"
          },
          "weight": 15
        }
      ],
      "displaySetSelectors": {
        "ankle-ap": {
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
                "contains": "Sprunggelenk"
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
        "ankle-lat": {
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
                "contains": "Sprunggelenk"
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
        "prior-ankle-ap": {
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
                "contains": "Sprunggelenk"
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
        "prior-ankle-lat": {
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
                "contains": "Sprunggelenk"
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
          "id": "dx-ankle-prior-stage",
          "name": "Sprunggelenk + VU",
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
                  "id": "ankle-ap"
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
                  "id": "ankle-lat"
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
                  "id": "prior-ankle-ap"
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
                  "id": "prior-ankle-lat"
                }
              ]
            }
          ]
        }
      ]
    },
    {
      "id": "dx-foot",
      "name": "Roentgen Fuß",
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
            "contains": "Fuß"
          },
          "weight": 15
        }
      ],
      "displaySetSelectors": {
        "foot-dp": {
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
                "contains": "Fuß"
              }
            },
            {
              "attribute": "SeriesDescription",
              "constraint": {
                "contains": "dp"
              }
            }
          ]
        },
        "foot-schraeg": {
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
                "contains": "Fuß"
              }
            },
            {
              "attribute": "SeriesDescription",
              "constraint": {
                "contains": "schräg"
              }
            }
          ]
        }
      },
      "stages": [
        {
          "id": "dx-foot-stage",
          "name": "Fuß dp+schraeg",
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
                  "id": "foot-dp"
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
                  "id": "foot-schraeg"
                }
              ]
            }
          ]
        }
      ]
    },
    {
      "id": "dx-foot-prior",
      "name": "Roentgen Fuß mit VU",
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
            "contains": "Fuß"
          },
          "weight": 15
        }
      ],
      "displaySetSelectors": {
        "foot-dp": {
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
                "contains": "Fuß"
              }
            },
            {
              "attribute": "SeriesDescription",
              "constraint": {
                "contains": "dp"
              }
            }
          ]
        },
        "foot-schraeg": {
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
                "contains": "Fuß"
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
        "prior-foot-dp": {
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
                "contains": "Fuß"
              }
            },
            {
              "attribute": "SeriesDescription",
              "constraint": {
                "contains": "dp"
              }
            }
          ]
        },
        "prior-foot-schraeg": {
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
                "contains": "Fuß"
              }
            },
            {
              "attribute": "SeriesDescription",
              "constraint": {
                "contains": "schräg"
              }
            }
          ]
        }
      },
      "stages": [
        {
          "id": "dx-foot-prior-stage",
          "name": "Fuß + VU",
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
                  "id": "foot-dp"
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
                  "id": "foot-schraeg"
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
                  "id": "prior-foot-dp"
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
                  "id": "prior-foot-schraeg"
                }
              ]
            }
          ]
        }
      ]
    },
    {
      "id": "dx-lower-leg",
      "name": "Roentgen Unterschenkel",
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
            "contains": "Unterschenkel"
          },
          "weight": 15
        }
      ],
      "displaySetSelectors": {
        "ll-ap": {
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
                "contains": "Unterschenkel"
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
        "ll-lat": {
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
                "contains": "Unterschenkel"
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
          "id": "dx-lower-leg-stage",
          "name": "Unterschenkel AP+LAT",
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
                  "id": "ll-ap"
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
                  "id": "ll-lat"
                }
              ]
            }
          ]
        }
      ]
    },
    {
      "id": "dx-lower-leg-prior",
      "name": "Roentgen Unterschenkel mit VU",
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
            "contains": "Unterschenkel"
          },
          "weight": 15
        }
      ],
      "displaySetSelectors": {
        "ll-ap": {
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
                "contains": "Unterschenkel"
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
        "ll-lat": {
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
                "contains": "Unterschenkel"
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
        "prior-ll-ap": {
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
                "contains": "Unterschenkel"
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
        "prior-ll-lat": {
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
                "contains": "Unterschenkel"
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
          "id": "dx-lower-leg-prior-stage",
          "name": "Unterschenkel + VU",
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
                  "id": "ll-ap"
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
                  "id": "ll-lat"
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
                  "id": "prior-ll-ap"
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
                  "id": "prior-ll-lat"
                }
              ]
            }
          ]
        }
      ]
    },
    {
      "id": "dx-sacrum",
      "name": "Roentgen Sacrum",
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
            "contains": "Sacrum"
          },
          "weight": 15
        }
      ],
      "displaySetSelectors": {
        "sacrum-lat": {
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
                "contains": "Sacrum"
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
        "sacrum-ap": {
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
                "contains": "Sacrum"
              }
            },
            {
              "attribute": "SeriesDescription",
              "constraint": {
                "contains": "AP"
              }
            }
          ]
        }
      },
      "stages": [
        {
          "id": "dx-sacrum-stage",
          "name": "Sacrum LAT+AP",
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
                  "id": "sacrum-lat"
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
                  "id": "sacrum-ap"
                }
              ]
            }
          ]
        }
      ]
    },
    {
      "id": "dx-sacrum-prior",
      "name": "Roentgen Sacrum mit VU",
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
            "contains": "Sacrum"
          },
          "weight": 15
        }
      ],
      "displaySetSelectors": {
        "sacrum-lat": {
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
                "contains": "Sacrum"
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
        "sacrum-ap": {
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
                "contains": "Sacrum"
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
        "prior-sacrum-lat": {
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
                "contains": "Sacrum"
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
        "prior-sacrum-ap": {
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
                "contains": "Sacrum"
              }
            },
            {
              "attribute": "SeriesDescription",
              "constraint": {
                "contains": "AP"
              }
            }
          ]
        }
      },
      "stages": [
        {
          "id": "dx-sacrum-prior-stage",
          "name": "Sacrum + VU",
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
                  "id": "sacrum-lat"
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
                  "id": "sacrum-ap"
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
                  "id": "prior-sacrum-lat"
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
                  "id": "prior-sacrum-ap"
                }
              ]
            }
          ]
        }
      ]
    },
    {
      "id": "dx-abdomen",
      "name": "Roentgen Abdomen leer",
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
            "contains": "Abdomen"
          },
          "weight": 15
        }
      ],
      "displaySetSelectors": {
        "abd-pa": {
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
                "contains": "Abdomen"
              }
            }
          ]
        }
      },
      "stages": [
        {
          "id": "dx-abdomen-stage",
          "name": "Abdomen PA",
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
                "viewportType": "stack",
                "toolGroupId": "default"
              },
              "displaySets": [
                {
                  "id": "abd-pa"
                }
              ]
            }
          ]
        }
      ]
    },
    {
      "id": "dx-abdomen-prior",
      "name": "Roentgen Abdomen mit VU",
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
            "contains": "Abdomen"
          },
          "weight": 15
        }
      ],
      "displaySetSelectors": {
        "abd-pa": {
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
                "contains": "Abdomen"
              }
            }
          ]
        },
        "prior-abd-pa": {
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
                "contains": "Abdomen"
              }
            }
          ]
        }
      },
      "stages": [
        {
          "id": "dx-abdomen-prior-stage",
          "name": "Abdomen + VU",
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
                  "id": "abd-pa"
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
                  "id": "prior-abd-pa"
                }
              ]
            }
          ]
        }
      ]
    },
    {
      "id": "mr-spine",
      "name": "MR Wirbelsaeule",
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
            "containsI": [
              "LWS",
              "HWS",
              "BWS",
              "Wirbels",
              "Spine",
              "ISG"
            ]
          },
          "weight": 15
        }
      ],
      "displaySetSelectors": {
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
        "stir": {
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
                "containsI": [
                  "stir",
                  "tirm"
                ]
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
        }
      },
      "stages": [
        {
          "id": "mr-spine-stage",
          "name": "WS 2x2",
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
                  "id": "t1-sag"
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
                  "id": "stir"
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
            }
          ]
        }
      ]
    },
    {
      "id": "mr-spine-prior",
      "name": "MR Wirbelsaeule mit VU",
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
            "containsI": [
              "LWS",
              "HWS",
              "BWS",
              "Wirbels",
              "Spine",
              "ISG"
            ]
          },
          "weight": 15
        }
      ],
      "displaySetSelectors": {
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
        "prior-t1-sag": {
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
        }
      },
      "stages": [
        {
          "id": "mr-spine-prior-stage",
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
                  "id": "t1-sag"
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
                  "id": "prior-t1-sag"
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
            }
          ]
        }
      ]
    },
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
            "containsI": [
              "Kopf",
              "Schädel",
              "Schaedel",
              "NNH",
              "Halsweichteil"
            ]
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
                "containsI": [
                  "flair",
                  "dark-fluid",
                  "space"
                ]
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
                "containsI": [
                  "dwi",
                  "trace",
                  "adc"
                ]
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
                "containsI": [
                  "km",
                  "contrast",
                  "gad",
                  "KM"
                ]
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
            "containsI": [
              "Kopf",
              "Schädel",
              "Schaedel",
              "NNH",
              "Halsweichteil"
            ]
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
                "containsI": [
                  "flair",
                  "dark-fluid",
                  "space"
                ]
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
                "containsI": [
                  "flair",
                  "dark-fluid",
                  "space"
                ]
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
            "containsI": [
              "subtraktion",
              "eMIP"
            ]
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
                "containsI": [
                  "km",
                  "KM",
                  "contrast",
                  "gad"
                ]
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
                "containsI": [
                  "subtraktion",
                  "eMIP",
                  "sub"
                ]
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
            "containsI": [
              "subtraktion",
              "eMIP"
            ]
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
    },
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
                "containsI": [
                  "pd",
                  "spir"
                ]
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
                "containsI": [
                  "pd",
                  "spir"
                ]
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
                "containsI": [
                  "pd",
                  "spir"
                ]
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
                "containsI": [
                  "pd",
                  "spir"
                ]
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
                "containsI": [
                  "pd",
                  "spir"
                ]
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
                "containsI": [
                  "pd",
                  "spir"
                ]
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
    },
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
            "containsI": [
              "Abdomen",
              "Oberbauch",
              "Leber",
              "MRCP",
              "Nieren",
              "Pankreas"
            ]
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
                "containsI": [
                  "t1",
                  "dixon",
                  "vibe",
                  "fl2d",
                  "dual_ffe",
                  "mDIXON"
                ]
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
                "containsI": [
                  "dwi",
                  "diff",
                  "tracew",
                  "adc"
                ]
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
            "containsI": [
              "Prostate",
              "Prostata",
              "Becken"
            ]
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
                "containsI": [
                  "dwi",
                  "diff",
                  "tracew",
                  "adc"
                ]
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
    },
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
                "containsI": [
                  "MIP Angio",
                  "Radial MIP"
                ]
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
                "containsI": [
                  "MIP Abdomen",
                  "MIP Pelvis",
                  "MIP tra 3D_mDIXON_MRA_Pelvis"
                ]
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
                "containsI": [
                  "MIP Oberschenkel",
                  "MIP ULeg",
                  "MIP tra 3D_mDIXON_MRA_ULeg"
                ]
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
                "containsI": [
                  "MIP Unterschenkel 1",
                  "MIP LLeg",
                  "MIP tra 3D_mDIXON_MRA_LLeg"
                ]
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
                "containsI": [
                  "vibe",
                  "mDIXON_FFE"
                ]
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
                "containsI": [
                  "abdomen",
                  "Pelvis"
                ]
              },
              "required": true
            },
            {
              "attribute": "SeriesDescription",
              "constraint": {
                "containsI": [
                  "SUB",
                  "mDIXON_MRA"
                ]
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
                "containsI": [
                  "upper_legs",
                  "ULeg"
                ]
              },
              "required": true
            },
            {
              "attribute": "SeriesDescription",
              "constraint": {
                "containsI": [
                  "SUB",
                  "mDIXON_MRA"
                ]
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
                "containsI": [
                  "II_Angio3D_legs",
                  "LLeg"
                ]
              },
              "required": true
            },
            {
              "attribute": "SeriesDescription",
              "constraint": {
                "containsI": [
                  "SUB",
                  "mDIXON_MRA"
                ]
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
                "containsI": [
                  "MIP Angio",
                  "Radial MIP"
                ]
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
                "containsI": [
                  "MIP Abdomen",
                  "MIP Pelvis",
                  "MIP tra 3D_mDIXON_MRA_Pelvis"
                ]
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
                "containsI": [
                  "MIP Oberschenkel",
                  "MIP ULeg",
                  "MIP tra 3D_mDIXON_MRA_ULeg"
                ]
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
                "containsI": [
                  "MIP Angio",
                  "Radial MIP"
                ]
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
                "containsI": [
                  "MIP Abdomen",
                  "MIP Pelvis",
                  "MIP tra 3D_mDIXON_MRA_Pelvis"
                ]
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
                "containsI": [
                  "MIP Oberschenkel",
                  "MIP ULeg",
                  "MIP tra 3D_mDIXON_MRA_ULeg"
                ]
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
    },
    {
      "id": "xa-default",
      "name": "DSA Default",
      "locked": false,
      "isPreset": true,
      "protocolMatchingRules": [
        {
          "attribute": "ModalitiesInStudy",
          "constraint": {
            "contains": "XA"
          },
          "required": true
        }
      ],
      "displaySetSelectors": {
        "xa-first": {
          "seriesMatchingRules": [
            {
              "attribute": "Modality",
              "constraint": {
                "equals": "XA"
              },
              "required": true
            }
          ]
        }
      },
      "stages": [
        {
          "id": "xa-default-stage",
          "name": "DSA 1x1",
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
                "viewportType": "stack",
                "toolGroupId": "default"
              },
              "displaySets": [
                {
                  "id": "xa-first"
                }
              ]
            }
          ]
        }
      ]
    },
    {
      "id": "xa-dsa-head",
      "name": "DSA Hirnangiographie",
      "locked": false,
      "isPreset": true,
      "protocolMatchingRules": [
        {
          "attribute": "ModalitiesInStudy",
          "constraint": {
            "contains": "XA"
          },
          "required": true
        },
        {
          "attribute": "seriesDescriptions",
          "constraint": {
            "contains": "Hirn"
          },
          "weight": 20
        },
        {
          "attribute": "seriesDescriptions",
          "constraint": {
            "contains": "zerebral"
          },
          "weight": 20
        },
        {
          "attribute": "seriesDescriptions",
          "constraint": {
            "contains": "Carotis"
          },
          "weight": 15
        },
        {
          "attribute": "seriesDescriptions",
          "constraint": {
            "contains": "cerebri"
          },
          "weight": 15
        }
      ],
      "displaySetSelectors": {
        "dsa-ap": {
          "seriesMatchingRules": [
            {
              "attribute": "Modality",
              "constraint": {
                "equals": "XA"
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
        "dsa-lat": {
          "seriesMatchingRules": [
            {
              "attribute": "Modality",
              "constraint": {
                "equals": "XA"
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
        },
        "dsa-1": {
          "seriesMatchingRules": [
            {
              "attribute": "Modality",
              "constraint": {
                "equals": "XA"
              },
              "required": true
            }
          ]
        },
        "dsa-2": {
          "seriesMatchingRules": [
            {
              "attribute": "Modality",
              "constraint": {
                "equals": "XA"
              },
              "required": true
            }
          ]
        }
      },
      "stages": [
        {
          "id": "xa-dsa-head-stage",
          "name": "DSA Hirn 2x2",
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
                  "id": "dsa-ap"
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
                  "id": "dsa-lat"
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
                  "id": "dsa-1"
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
                  "id": "dsa-2"
                }
              ]
            }
          ]
        }
      ]
    },
    {
      "id": "xa-dsa-head-prior",
      "name": "DSA Hirnangiographie mit VU",
      "locked": false,
      "isPreset": true,
      "numberOfPriorsReferenced": 1,
      "protocolMatchingRules": [
        {
          "attribute": "ModalitiesInStudy",
          "constraint": {
            "contains": "XA"
          },
          "required": true
        },
        {
          "attribute": "seriesDescriptions",
          "constraint": {
            "contains": "Hirn"
          },
          "weight": 20
        },
        {
          "attribute": "seriesDescriptions",
          "constraint": {
            "contains": "zerebral"
          },
          "weight": 20
        },
        {
          "attribute": "seriesDescriptions",
          "constraint": {
            "contains": "Carotis"
          },
          "weight": 15
        }
      ],
      "displaySetSelectors": {
        "dsa-ap": {
          "seriesMatchingRules": [
            {
              "attribute": "Modality",
              "constraint": {
                "equals": "XA"
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
        "dsa-lat": {
          "seriesMatchingRules": [
            {
              "attribute": "Modality",
              "constraint": {
                "equals": "XA"
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
        },
        "prior-dsa-ap": {
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
                "equals": "XA"
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
        "prior-dsa-lat": {
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
                "equals": "XA"
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
          "id": "xa-dsa-head-prior-stage",
          "name": "DSA Hirn + VU",
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
                  "id": "dsa-ap"
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
                  "id": "dsa-lat"
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
                  "id": "prior-dsa-ap"
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
                  "id": "prior-dsa-lat"
                }
              ]
            }
          ]
        }
      ]
    },
    {
      "id": "xa-dsa-carotid",
      "name": "DSA Karotis",
      "locked": false,
      "isPreset": true,
      "protocolMatchingRules": [
        {
          "attribute": "ModalitiesInStudy",
          "constraint": {
            "contains": "XA"
          },
          "required": true
        },
        {
          "attribute": "seriesDescriptions",
          "constraint": {
            "contains": "Carotis"
          },
          "weight": 20
        },
        {
          "attribute": "seriesDescriptions",
          "constraint": {
            "contains": "Karotis"
          },
          "weight": 20
        }
      ],
      "displaySetSelectors": {
        "dsa-ap": {
          "seriesMatchingRules": [
            {
              "attribute": "Modality",
              "constraint": {
                "equals": "XA"
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
        "dsa-lat": {
          "seriesMatchingRules": [
            {
              "attribute": "Modality",
              "constraint": {
                "equals": "XA"
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
          "id": "xa-dsa-carotid-stage",
          "name": "DSA Karotis 1x2",
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
                  "id": "dsa-ap"
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
                  "id": "dsa-lat"
                }
              ]
            }
          ]
        }
      ]
    },
    {
      "id": "xa-dsa-aorta",
      "name": "DSA Aorta",
      "locked": false,
      "isPreset": true,
      "protocolMatchingRules": [
        {
          "attribute": "ModalitiesInStudy",
          "constraint": {
            "contains": "XA"
          },
          "required": true
        },
        {
          "attribute": "seriesDescriptions",
          "constraint": {
            "contains": "Aorta"
          },
          "weight": 20
        }
      ],
      "displaySetSelectors": {
        "dsa-ap": {
          "seriesMatchingRules": [
            {
              "attribute": "Modality",
              "constraint": {
                "equals": "XA"
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
        "dsa-lat": {
          "seriesMatchingRules": [
            {
              "attribute": "Modality",
              "constraint": {
                "equals": "XA"
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
          "id": "xa-dsa-aorta-stage",
          "name": "DSA Aorta 1x2",
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
                  "id": "dsa-ap"
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
                  "id": "dsa-lat"
                }
              ]
            }
          ]
        }
      ]
    },
    {
      "id": "xa-dsa-peripheral",
      "name": "DSA Peripher (Becken-Bein)",
      "locked": false,
      "isPreset": true,
      "protocolMatchingRules": [
        {
          "attribute": "ModalitiesInStudy",
          "constraint": {
            "contains": "XA"
          },
          "required": true
        },
        {
          "attribute": "seriesDescriptions",
          "constraint": {
            "contains": "Peripher"
          },
          "weight": 20
        },
        {
          "attribute": "seriesDescriptions",
          "constraint": {
            "contains": "Becken"
          },
          "weight": 15
        },
        {
          "attribute": "seriesDescriptions",
          "constraint": {
            "contains": "Bein"
          },
          "weight": 15
        },
        {
          "attribute": "seriesDescriptions",
          "constraint": {
            "contains": "Femoral"
          },
          "weight": 15
        },
        {
          "attribute": "seriesDescriptions",
          "constraint": {
            "contains": "Poplitea"
          },
          "weight": 15
        }
      ],
      "displaySetSelectors": {
        "dsa-1": {
          "seriesMatchingRules": [
            {
              "attribute": "Modality",
              "constraint": {
                "equals": "XA"
              },
              "required": true
            }
          ]
        },
        "dsa-2": {
          "seriesMatchingRules": [
            {
              "attribute": "Modality",
              "constraint": {
                "equals": "XA"
              },
              "required": true
            }
          ]
        }
      },
      "stages": [
        {
          "id": "xa-dsa-peripheral-stage",
          "name": "DSA Peripher 1x2",
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
                  "id": "dsa-1"
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
                  "id": "dsa-2"
                }
              ]
            }
          ]
        }
      ]
    },
    {
      "id": "xa-dsa-coronary",
      "name": "DSA Coronary (Herzkatheter)",
      "locked": false,
      "isPreset": true,
      "protocolMatchingRules": [
        {
          "attribute": "ModalitiesInStudy",
          "constraint": {
            "contains": "XA"
          },
          "required": true
        },
        {
          "attribute": "seriesDescriptions",
          "constraint": {
            "contains": "Coronary"
          },
          "weight": 20
        },
        {
          "attribute": "seriesDescriptions",
          "constraint": {
            "contains": "Koronar"
          },
          "weight": 20
        },
        {
          "attribute": "seriesDescriptions",
          "constraint": {
            "contains": "Herz"
          },
          "weight": 15
        },
        {
          "attribute": "seriesDescriptions",
          "constraint": {
            "contains": "LAD"
          },
          "weight": 15
        },
        {
          "attribute": "seriesDescriptions",
          "constraint": {
            "contains": "RCA"
          },
          "weight": 15
        },
        {
          "attribute": "seriesDescriptions",
          "constraint": {
            "contains": "CX"
          },
          "weight": 15
        }
      ],
      "displaySetSelectors": {
        "dsa-1": {
          "seriesMatchingRules": [
            {
              "attribute": "Modality",
              "constraint": {
                "equals": "XA"
              },
              "required": true
            }
          ]
        },
        "dsa-2": {
          "seriesMatchingRules": [
            {
              "attribute": "Modality",
              "constraint": {
                "equals": "XA"
              },
              "required": true
            }
          ]
        }
      },
      "stages": [
        {
          "id": "xa-dsa-coronary-stage",
          "name": "DSA Coronary 1x2",
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
                  "id": "dsa-1"
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
                  "id": "dsa-2"
                }
              ]
            }
          ]
        }
      ]
    }
  ],
  "defaultHangingProtocolName": "ct-default",
  "hotkeys": [
    {
      "command": "incrementActiveViewport",
      "label": "Next Viewport",
      "keys": [
        "right"
      ]
    },
    {
      "command": "decrementActiveViewport",
      "label": "Previous Viewport",
      "keys": [
        "left"
      ]
    },
    {
      "command": "rotateViewportCW",
      "label": "Rotate Right",
      "keys": [
        "r"
      ]
    },
    {
      "command": "flipViewportHorizontal",
      "label": "Flip H",
      "keys": [
        "h"
      ]
    },
    {
      "command": "invertViewport",
      "label": "Invert",
      "keys": [
        "i"
      ]
    }
  ]
};
