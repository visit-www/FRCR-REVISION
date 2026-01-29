-- TNM Phase 2 Verification - Production Sync Migration
-- Generated for PostgreSQL (Vercel Postgres / Neon)
-- Run this on your production database to sync changes made locally
--
-- NOTE: Disease IDs differ between local SQLite and production PostgreSQL
-- Local ID 89 = Production ID 98 (Cervical Lymph Nodes)
-- Local ID 97 = Production ID 92 (Staging Principles)

-- ============================================================
-- DISEASE: Cervical Lymph Nodes and Unknown Primary
-- Production ID: 98 (Local ID: 89)
-- ============================================================

-- Update T definitions to T0 only
UPDATE ajcc_staging_data
SET tnm_data_json = jsonb_set(
    tnm_data_json::jsonb,
    '{t_definitions}',
    '[{"subsite": "Default", "categories": [{"category": "T0", "criteria": "No identifiable primary tumor"}]}]'::jsonb
)::text
WHERE disease_site_id = 98;

-- Update stage groups to T0-only entries
UPDATE ajcc_staging_data
SET tnm_data_json = jsonb_set(
    tnm_data_json::jsonb,
    '{stage_groups}',
    '[
        {"T": "T0", "N": "N1", "M": "M0", "stage": "III"},
        {"T": "T0", "N": "N2", "M": "M0", "stage": "IVA"},
        {"T": "T0", "N": "N3", "M": "M0", "stage": "IVB"},
        {"T": "T0", "N": "Any N", "M": "M1", "stage": "IVC"}
    ]'::jsonb
)::text
WHERE disease_site_id = 98;

-- Add curated quick reference notes for Cervical Lymph Nodes
UPDATE ajcc_staging_data
SET curated_quick_reference_html = '<div class="alert alert-info">
<h5><i class="fas fa-info-circle me-2"></i>Cervical Lymph Node Cancer with Unknown Primary</h5>

<p>Sometimes cancer is found in neck (cervical) lymph nodes, but no primary tumor can be identified despite proper testing.</p>

<h6>How staging works in this situation:</h6>
<ul>
<li>T0 is used exclusively - no identifiable primary tumor</li>
<li>The calculator does not guess the tumor site</li>
<li>These cases are staged using: <strong>Cervical Node and Unknown Primary</strong></li>
</ul>

<p>This system focuses on lymph node involvement and provides more accurate staging and prognosis.</p>

<h6>Important exceptions:</h6>
<ul>
<li><strong>p16 positive (HPV-related)</strong> → staged as oropharyngeal cancer</li>
<li><strong>EBV positive</strong> → staged as nasopharyngeal cancer</li>
</ul>

<p><em>Key takeaway: If the primary tumor is unknown, staging is based on lymph nodes — unless biology clearly identifies the cancer''s origin.</em></p>
</div>'
WHERE disease_site_id = 98;

-- ============================================================
-- DISEASE: Staging Principles of Head and Neck Cancers
-- Production ID: 92 (Local ID: 97)
-- (Info-only entry - no TNM staging, just reference content)
-- ============================================================

-- Remove TNM data entirely (this is an info-only page)
UPDATE ajcc_staging_data
SET tnm_data_json = NULL
WHERE disease_site_id = 92;

-- Add curated quick reference notes for Staging Principles
UPDATE ajcc_staging_data
SET curated_quick_reference_html = '<div class="alert alert-primary">
<h4><i class="fas fa-book-medical me-2"></i>AJCC 8th Edition – Head & Neck Cancer Staging Key Points</h4>

<h5>1. Structural Changes</h5>
<ul>
<li>Staging now reflects <strong>biology, not just anatomy</strong></li>
<li>Pharynx split into: Nasopharynx, HPV-negative oropharynx/hypopharynx, HPV-positive oropharynx</li>
<li>Cancer of Unknown Primary has its own staging system</li>
</ul>

<h5>2. Cancer of Unknown Primary</h5>
<ul>
<li>T0 removed from most H&N sites (oral cavity, larynx, hypopharynx)</li>
<li>Cervical node metastasis with no primary → staged as "Cervical Node and Unknown Primary"</li>
<li>Exceptions: p16+ → HPV-associated oropharynx; EBV+ → nasopharynx</li>
</ul>

<h5>3. HPV-Positive Oropharynx</h5>
<ul>
<li>p16 overexpression used as HPV surrogate marker</li>
<li>p16+ and p16− cancers staged separately</li>
<li>HPV+ cancers: younger patients, better prognosis</li>
</ul>

<h5>4. T Category Changes</h5>
<ul>
<li><strong>Oral cavity:</strong> Depth of Invasion (DOI) added - T increases every 5mm</li>
<li><strong>Skin:</strong> T3 includes depth >6mm or perineural invasion</li>
<li>If uncertain → assign lower T category</li>
</ul>

<h5>5. N Category Changes</h5>
<ul>
<li><strong>Extranodal Extension (ENE)</strong> now in N staging</li>
<li>Clinical ENE: requires physical signs (skin invasion, nerve dysfunction)</li>
<li>Pathological ENE: tumor extends beyond node capsule</li>
<li>If ENE uncertain → classify as ENE-negative</li>
</ul>
</div>'
WHERE disease_site_id = 92;

-- ============================================================
-- CLEANUP: Remove any IntelligentTNMData that was incorrectly added
-- ============================================================

DELETE FROM intelligent_tnm_data WHERE disease_site_id IN (92, 98);

-- ============================================================
-- VERIFICATION QUERIES (run these to confirm changes)
-- ============================================================

-- Check Cervical Lymph Nodes T definitions and stage groups
-- SELECT disease_site_id, 
--        tnm_data_json::jsonb->'t_definitions' as t_defs,
--        tnm_data_json::jsonb->'stage_groups' as stages
-- FROM ajcc_staging_data WHERE disease_site_id = 98;

-- Check Staging Principles has no TNM data
-- SELECT disease_site_id, tnm_data_json IS NULL as no_tnm_data
-- FROM ajcc_staging_data WHERE disease_site_id = 92;

-- Check curated notes exist
-- SELECT disease_site_id, LEFT(curated_quick_reference_html, 100) 
-- FROM ajcc_staging_data WHERE disease_site_id IN (92, 98);

-- Confirm IntelligentTNMData deleted
-- SELECT * FROM intelligent_tnm_data WHERE disease_site_id IN (92, 98);
