# AJCC TNM Database Schema

## Entity Relationship Diagram

```
┌─────────────────────┐       ┌─────────────────────┐
│   AJCCBodySection   │       │  AJCCDiagnosisYear  │
├─────────────────────┤       ├─────────────────────┤
│ id (PK)             │       │ id (PK)             │
│ section_name        │       │ year                │
│ slug                │       │ is_default          │
│ display_order       │       │ created_at          │
│ created_at          │       └─────────┬───────────┘
│ updated_at          │                 │
└─────────┬───────────┘                 │
          │                             │
          │ 1:N                         │ 1:N
          ▼                             │
┌─────────────────────┐                 │
│   AJCCDiseaseSite   │                 │
├─────────────────────┤                 │
│ id (PK)             │                 │
│ body_section_id (FK)│◀────────────────┤
│ disease_name        │                 │
│ slug                │                 │
│ ajcc_url_path       │                 │
│ created_at          │                 │
│ updated_at          │                 │
└─────────┬───────────┘                 │
          │                             │
          │ 1:N                         │
          ▼                             │
┌─────────────────────┐                 │
│  AJCCStagingData    │◀────────────────┘
├─────────────────────┤
│ id (PK)             │      ┌─────────────────────┐
│ disease_site_id (FK)│      │       User          │
│ diagnosis_year_id   │      │   (Host App)        │
│ tnm_data_json       │      └─────────┬───────────┘
│ cancers_staged_json │                │
│ ... (other JSON)    │                │
│ section_1_html      │                │
│ ... (other HTML)    │                │
│ extracted_by_user_id│◀───────────────┘
│ extracted_at        │
│ data_version        │
└─────────┬───────────┘
          │
          │ N:1
          │
┌─────────┴───────────┐
│ AJCCDiseaseMapping  │
├─────────────────────┤        ┌─────────────────────┐
│ id (PK)             │        │ AJCCStagingTimePrefix│
│ disease_site_id (FK)│        ├─────────────────────┤
│ frcr_module         │        │ id (PK)             │
│ body_part           │        │ prefix              │
│ notes               │        │ name                │
│ created_at          │        │ description         │
│ updated_at          │        │ display_order       │
└─────────────────────┘        │ created_at          │
                               └─────────────────────┘
```

## Table Definitions

### AJCCBodySection

AJCC body sections (e.g., Thorax, Head and Neck).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PK | Primary key |
| section_name | String(100) | NOT NULL, UNIQUE | Display name |
| slug | String(100) | NOT NULL, UNIQUE, INDEX | URL-safe identifier |
| display_order | Integer | DEFAULT 0 | Sort order |
| created_at | DateTime | DEFAULT now() | Creation timestamp |
| updated_at | DateTime | DEFAULT now() | Last update timestamp |

### AJCCDiseaseSite

Diseases within body sections (e.g., Lung, Breast).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PK | Primary key |
| body_section_id | Integer | FK, NOT NULL, INDEX | Parent section |
| disease_name | String(200) | NOT NULL | Display name |
| slug | String(200) | NOT NULL, INDEX | URL-safe identifier |
| ajcc_url_path | String(300) | NOT NULL | AJCC API path |
| created_at | DateTime | DEFAULT now() | Creation timestamp |
| updated_at | DateTime | DEFAULT now() | Last update timestamp |

**Unique Constraint**: `(body_section_id, slug)`

### AJCCDiagnosisYear

Available diagnosis years.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PK | Primary key |
| year | Integer | NOT NULL, UNIQUE | Year (2024, 2025, 2026) |
| is_default | Boolean | DEFAULT FALSE, INDEX | Default year flag |
| created_at | DateTime | DEFAULT now() | Creation timestamp |

### AJCCStagingData

Main TNM staging data storage.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PK | Primary key |
| disease_site_id | Integer | FK, NOT NULL, INDEX | Disease reference |
| diagnosis_year_id | Integer | FK, NOT NULL, INDEX | Year reference |
| **JSON Fields** |
| tnm_data_json | Text | NULLABLE | T, N, M definitions + stage groups |
| cancers_staged_json | Text | NULLABLE | Cancers staged list |
| cancers_not_staged_json | Text | NULLABLE | Cancers not staged |
| summary_changes_json | Text | NULLABLE | Changes from previous edition |
| primary_sites_json | Text | NULLABLE | ICD-O codes |
| histopathologic_types_json | Text | NULLABLE | Histopathology info |
| imaging_workup_json | Text | NULLABLE | Imaging workup data |
| staging_rules_json | Text | NULLABLE | Staging rules |
| common_scenarios_json | Text | NULLABLE | Common scenarios |
| notes_json | Text | NULLABLE | Explanatory notes |
| **HTML Fields (Legacy)** |
| section_1_quick_reference_html | Text | NULLABLE | Section 1 HTML |
| section_2_cancers_staged_html | Text | NULLABLE | Section 2 HTML |
| section_3_cancers_not_staged_html | Text | NULLABLE | Section 3 HTML |
| section_4_summary_changes_html | Text | NULLABLE | Section 4 HTML |
| section_5_primary_site_html | Text | NULLABLE | Section 5 HTML |
| section_6_histopathologic_type_html | Text | NULLABLE | Section 6 HTML |
| section_7_clinical_staging_workup_html | Text | NULLABLE | Section 7 HTML |
| section_8_staging_rules_html | Text | NULLABLE | Section 8 HTML |
| section_9_common_scenarios_html | Text | NULLABLE | Section 9 HTML |
| section_10_explanatory_notes_html | Text | NULLABLE | Section 10 HTML |
| **Metadata** |
| raw_html_content | Text | NULLABLE | Original full HTML |
| extracted_at | DateTime | DEFAULT now() | Extraction timestamp |
| extracted_by_user_id | Integer | FK, NULLABLE | User who extracted |
| last_updated_at | DateTime | DEFAULT now() | Last update timestamp |
| data_version | Integer | DEFAULT 2 | 1=HTML, 2=JSON+HTML |

**Unique Constraint**: `(disease_site_id, diagnosis_year_id)`
**Index**: `idx_disease_year`

### AJCCDiseaseMapping

Maps AJCC diseases to app modules/body parts.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PK | Primary key |
| disease_site_id | Integer | FK, NOT NULL, INDEX | Disease reference |
| frcr_module | Enum(FRCRModule) | NULLABLE, INDEX | App module mapping |
| body_part | Enum(BodyPart) | NULLABLE, INDEX | App body part mapping |
| notes | Text | NULLABLE | Admin notes |
| created_at | DateTime | DEFAULT now() | Creation timestamp |
| updated_at | DateTime | DEFAULT now() | Last update timestamp |

**Indexes**: `idx_disease_frcr_module`, `idx_disease_body_part`

### AJCCStagingTimePrefix

Standard staging time prefixes.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PK | Primary key |
| prefix | String(5) | NOT NULL, UNIQUE | Prefix code (c, p, yc, yp, r, a) |
| name | String(50) | NOT NULL | Display name |
| description | Text | NULLABLE | Full description |
| display_order | Integer | DEFAULT 0 | Sort order |
| created_at | DateTime | DEFAULT now() | Creation timestamp |

## JSON Data Structures

### tnm_data_json

```json
{
  "title": "Lung Cancer",
  "t_definitions": [
    {
      "subsite": "Default",
      "categories": [
        {"category": "TX", "criteria": "Primary tumor cannot be assessed"},
        {"category": "T0", "criteria": "No evidence of primary tumor"},
        {"category": "Tis", "criteria": "Carcinoma in situ"},
        {"category": "T1", "criteria": "Tumor <= 3 cm..."}
      ]
    }
  ],
  "n_definitions": {
    "clinical": [
      {"category": "NX", "criteria": "Regional lymph nodes cannot be assessed"},
      {"category": "N0", "criteria": "No regional lymph node metastasis"}
    ],
    "pathological": [...]
  },
  "m_definitions": [
    {"category": "M0", "criteria": "No distant metastasis"},
    {"category": "M1", "criteria": "Distant metastasis"}
  ],
  "stage_groups": [
    {"T": "T1", "N": "N0", "M": "M0", "stage": "IA"},
    {"T": "T2", "N": "N1", "M": "M0", "stage": "IIB"},
    {"T": "Any T", "N": "Any N", "M": "M1", "stage": "IV"}
  ],
  "notes": ["Additional staging notes..."]
}
```

## Indexes for Performance

### Calculator Lookups

```sql
-- Fast stage group lookups
CREATE INDEX idx_staging_calculator ON ajcc_staging_data 
    USING GIN (tnm_data_json);
```

### Browse Queries

```sql
-- Fast disease listing
CREATE INDEX idx_disease_section ON ajcc_disease_site (body_section_id, disease_name);

-- Fast year filtering
CREATE INDEX idx_staging_year ON ajcc_staging_data (disease_site_id, diagnosis_year_id);
```
