# Data Formats Reference

## Overview

The AJCC TNM module stores data in both JSON (primary) and HTML (legacy) formats.

## JSON Schemas

### tnm_data_json

The main TNM staging data structure.

```json
{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "TNM Staging Data",
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": "Disease name"
        },
        "t_definitions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "subsite": {
                        "type": "string",
                        "description": "Subsite name or 'Default'"
                    },
                    "categories": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "category": {
                                    "type": "string",
                                    "pattern": "^T(X|is|[0-4][ab]?)$"
                                },
                                "criteria": {
                                    "type": "string"
                                }
                            }
                        }
                    }
                }
            }
        },
        "n_definitions": {
            "type": "object",
            "properties": {
                "clinical": {
                    "type": "array",
                    "items": {
                        "$ref": "#/definitions/tnm_category"
                    }
                },
                "pathological": {
                    "type": "array",
                    "items": {
                        "$ref": "#/definitions/tnm_category"
                    }
                }
            }
        },
        "m_definitions": {
            "type": "array",
            "items": {
                "$ref": "#/definitions/tnm_category"
            }
        },
        "stage_groups": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "T": {"type": "string"},
                    "N": {"type": "string"},
                    "M": {"type": "string"},
                    "stage": {"type": "string"}
                }
            }
        },
        "notes": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "definitions": {
        "tnm_category": {
            "type": "object",
            "properties": {
                "category": {"type": "string"},
                "criteria": {"type": "string"}
            }
        }
    }
}
```

### Example tnm_data_json

```json
{
    "title": "Lung Cancer - Non-Small Cell",
    "t_definitions": [
        {
            "subsite": "Default",
            "categories": [
                {
                    "category": "TX",
                    "criteria": "Primary tumor cannot be assessed, or tumor proven by the presence of malignant cells in sputum or bronchial washings but not visualized by imaging or bronchoscopy"
                },
                {
                    "category": "T0",
                    "criteria": "No evidence of primary tumor"
                },
                {
                    "category": "Tis",
                    "criteria": "Carcinoma in situ: Squamous cell carcinoma in situ (SCIS) or Adenocarcinoma in situ (AIS)"
                },
                {
                    "category": "T1",
                    "criteria": "Tumor 3 cm or less in greatest dimension, surrounded by lung or visceral pleura, without bronchoscopic evidence of invasion more proximal than the lobar bronchus"
                }
            ]
        }
    ],
    "n_definitions": {
        "clinical": [
            {"category": "NX", "criteria": "Regional lymph nodes cannot be assessed"},
            {"category": "N0", "criteria": "No regional lymph node metastasis"},
            {"category": "N1", "criteria": "Metastasis in ipsilateral peribronchial and/or ipsilateral hilar lymph nodes"}
        ],
        "pathological": [
            {"category": "pNX", "criteria": "Regional lymph nodes cannot be assessed"},
            {"category": "pN0", "criteria": "No regional lymph node metastasis"}
        ]
    },
    "m_definitions": [
        {"category": "M0", "criteria": "No distant metastasis"},
        {"category": "M1", "criteria": "Distant metastasis"},
        {"category": "M1a", "criteria": "Separate tumor nodule(s) in a contralateral lobe"},
        {"category": "M1b", "criteria": "Single extrathoracic metastasis"},
        {"category": "M1c", "criteria": "Multiple extrathoracic metastases"}
    ],
    "stage_groups": [
        {"T": "Tis", "N": "N0", "M": "M0", "stage": "0"},
        {"T": "T1a", "N": "N0", "M": "M0", "stage": "IA1"},
        {"T": "T1b", "N": "N0", "M": "M0", "stage": "IA2"},
        {"T": "T1c", "N": "N0", "M": "M0", "stage": "IA3"},
        {"T": "T2a", "N": "N0", "M": "M0", "stage": "IB"},
        {"T": "T2b", "N": "N0", "M": "M0", "stage": "IIA"},
        {"T": "T1, T2", "N": "N1", "M": "M0", "stage": "IIB"},
        {"T": "T3", "N": "N0", "M": "M0", "stage": "IIB"},
        {"T": "Any T", "N": "Any N", "M": "M1", "stage": "IV"}
    ],
    "notes": [
        "The uncommon superficial spreading tumor of any size with its invasive component limited to the bronchial wall is classified as T1a."
    ]
}
```

### cancers_staged_json

```json
{
    "title": "Cancers Staged Using This Staging System",
    "cancers": [
        "Non-small cell lung carcinoma (NSCLC)",
        "Large cell neuroendocrine carcinoma",
        "Bronchopulmonary carcinoid tumors"
    ],
    "text": "Full text description..."
}
```

### cancers_not_staged_json

```json
{
    "title": "Cancers Not Staged Using This Staging System",
    "exclusions": [
        {
            "cancer_type": "Small cell lung carcinoma",
            "staged_according_to": "Small Cell Lung Cancer Staging System"
        },
        {
            "cancer_type": "Pleural mesothelioma",
            "staged_according_to": "Pleural Mesothelioma Staging System"
        }
    ]
}
```

### summary_changes_json

```json
{
    "title": "Summary of Changes",
    "changes": [
        {
            "change": "T category definitions",
            "details": "Size cutpoints were modified for T1 and T2",
            "level_of_evidence": "Level I"
        }
    ]
}
```

### primary_sites_json

```json
{
    "title": "Identification of Primary Site",
    "sites": [
        {"icd_o_code": "C34.0", "description": "Main bronchus"},
        {"icd_o_code": "C34.1", "description": "Upper lobe, lung"},
        {"icd_o_code": "C34.2", "description": "Middle lobe, lung"},
        {"icd_o_code": "C34.3", "description": "Lower lobe, lung"}
    ],
    "notes": []
}
```

### staging_rules_json

```json
{
    "title": "Staging Rules",
    "rules": [
        {
            "topic": "Clinical staging",
            "rule": "Clinical staging is based on all information available prior to first definitive treatment"
        },
        {
            "topic": "Multiple tumors",
            "rule": "Each tumor should be staged independently"
        }
    ]
}
```

## Stage Group Matching

The stage calculator uses pattern matching:

| Pattern | Matches |
|---------|---------|
| `T1` | Exact match "T1" |
| `T1, T2, T3` | Any of T1, T2, or T3 |
| `Any T` | Any T value |
| `T1a, T1b, T1c` | Any T1 subtype |

## Data Version

| Version | Description |
|---------|-------------|
| 1 | HTML only (legacy) |
| 2 | JSON + HTML (current) |

The `data_version` field in `AJCCStagingData` indicates the format.
