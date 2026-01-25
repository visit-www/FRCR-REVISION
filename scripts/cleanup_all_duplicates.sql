-- ============================================
-- STEP 1: Identify ALL duplicates across sections
-- ============================================

-- Check all sections and their disease sites
SELECT 
    bs.section_name,
    bs.slug as section_slug,
    ds.id,
    ds.disease_name,
    ds.slug as disease_slug,
    ds.ajcc_url_path
FROM ajcc_disease_site ds
JOIN ajcc_body_section bs ON ds.body_section_id = bs.id
ORDER BY bs.section_name, ds.disease_name;

-- ============================================
-- STEP 2: Delete old/duplicate slugs per section
-- ============================================

-- HEAD AND NECK - Clean duplicates
DELETE FROM ajcc_disease_site WHERE slug IN (
    'unknown-primary-head-neck',
    'hypopharynx', 
    'lip',
    'lip-and-oral-cavity',
    'oropharynx',
    'oropharynx-p16-negative',
    'hpv-mediated-p16-oropharyngeal-cancer',
    'nasal-cavity',
    'major-salivary-glands'
) AND body_section_id = (SELECT id FROM ajcc_body_section WHERE slug = 'head-and-neck');

-- UPPER GI - Clean old slugs
DELETE FROM ajcc_disease_site WHERE slug IN (
    'esophagus'  -- Now esophagus-and-esophagogastric-junction
) AND body_section_id = (SELECT id FROM ajcc_body_section WHERE slug = 'upper-gastrointestinal-tract');

-- LOWER GI - Clean old slugs
DELETE FROM ajcc_disease_site WHERE slug IN (
    'colon',
    'rectum',         -- Now combined as colon-and-rectum
    'anal-canal'      -- Now 'anus'
) AND body_section_id = (SELECT id FROM ajcc_body_section WHERE slug = 'lower-gastrointestinal-tract');

-- HEPATOBILIARY - Clean old slugs
DELETE FROM ajcc_disease_site WHERE slug IN (
    'pancreas'  -- Now exocrine-pancreas
) AND body_section_id = (SELECT id FROM ajcc_body_section WHERE slug = 'hepatobiliary-system');

-- NEUROENDOCRINE - Clean old slugs
DELETE FROM ajcc_disease_site WHERE slug IN (
    'net-stomach',
    'net-duodenum',
    'net-jejunum-ileum',
    'net-appendix',
    'net-colon-rectum',
    'net-pancreas'
) AND body_section_id = (SELECT id FROM ajcc_body_section WHERE slug = 'neuroendocrine-tumors');

-- THORAX - Clean old slugs
DELETE FROM ajcc_disease_site WHERE slug IN (
    'pleural-mesothelioma'  -- Now diffuse-pleural-mesothelioma
) AND body_section_id = (SELECT id FROM ajcc_body_section WHERE slug = 'thorax');

-- SOFT TISSUE SARCOMA - Clean old slugs
DELETE FROM ajcc_disease_site WHERE slug IN (
    'soft-tissue-head-neck',
    'soft-tissue-trunk-extremities',
    'soft-tissue-abdomen-thorax',
    'soft-tissue-retroperitoneum',
    'gist'
) AND body_section_id = (SELECT id FROM ajcc_body_section WHERE slug = 'soft-tissue-sarcoma');

-- SKIN - Clean old slugs
DELETE FROM ajcc_disease_site WHERE slug IN (
    'melanoma',
    'merkel-cell',
    'cutaneous-scc'
) AND body_section_id = (SELECT id FROM ajcc_body_section WHERE slug = 'skin');

-- FEMALE REPRODUCTIVE - Clean old slugs
DELETE FROM ajcc_disease_site WHERE slug IN (
    'cervix',
    'corpus-uteri',
    'corpus-uteri-sarcoma',
    'ovary',
    'gestational-trophoblastic'
) AND body_section_id = (SELECT id FROM ajcc_body_section WHERE slug = 'female-reproductive-organs');

-- URINARY TRACT - Clean old slugs
DELETE FROM ajcc_disease_site WHERE slug IN (
    'renal-pelvis-ureter',
    'bladder'
) AND body_section_id = (SELECT id FROM ajcc_body_section WHERE slug = 'urinary-tract');

-- OPHTHALMIC - Clean old slugs
DELETE FROM ajcc_disease_site WHERE slug IN (
    'lacrimal-gland'  -- Now lacrimal-gland-carcinoma
) AND body_section_id = (SELECT id FROM ajcc_body_section WHERE slug = 'ophthalmic-sites');

-- CNS - Clean old slugs
DELETE FROM ajcc_disease_site WHERE slug IN (
    'brain'  -- Now brain-and-spinal-cord
) AND body_section_id = (SELECT id FROM ajcc_body_section WHERE slug = 'central-nervous-system');

-- ENDOCRINE - Clean old slugs (note: throid is AJCC's typo, keep it)
DELETE FROM ajcc_disease_site WHERE slug IN (
    'thyroid-differentiated',
    'adrenal-cortical'
) AND body_section_id = (SELECT id FROM ajcc_body_section WHERE slug = 'endocrine-system');

-- HEMATOLOGIC - Clean old slugs
DELETE FROM ajcc_disease_site WHERE slug IN (
    'lymphomas',
    'cutaneous-lymphomas'
) AND body_section_id = (SELECT id FROM ajcc_body_section WHERE slug = 'hematologic-malignancies');

-- ============================================
-- STEP 3: Verify final counts
-- ============================================
SELECT 
    bs.section_name,
    COUNT(ds.id) as disease_count
FROM ajcc_body_section bs
LEFT JOIN ajcc_disease_site ds ON ds.body_section_id = bs.id
GROUP BY bs.section_name, bs.slug
ORDER BY bs.section_name;
