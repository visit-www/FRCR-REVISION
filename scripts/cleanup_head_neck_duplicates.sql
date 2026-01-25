-- Cleanup duplicate/old Head and Neck disease sites in Neon
-- Run this after the curated columns migration

-- First, check what duplicates exist
SELECT id, disease_name, slug, ajcc_url_path 
FROM ajcc_disease_site 
WHERE body_section_id = (SELECT id FROM ajcc_body_section WHERE slug = 'head-and-neck')
ORDER BY disease_name;

-- Delete old entries that should be removed
-- Note: This will fail if they have staging_data attached. 
-- If so, delete staging_data first or update the staging_data to point to correct entries.

-- Remove "Unknown Primary of the Head and Neck" (old entry, keep "Cervical Lymph Nodes and Unknown Primary...")
DELETE FROM ajcc_disease_site 
WHERE slug = 'unknown-primary-head-neck' 
AND body_section_id = (SELECT id FROM ajcc_body_section WHERE slug = 'head-and-neck');

-- Remove standalone "Hypopharynx" (it's now part of "Oropharynx (HPV-Independent) and Hypopharynx")
DELETE FROM ajcc_disease_site 
WHERE slug = 'hypopharynx' 
AND body_section_id = (SELECT id FROM ajcc_body_section WHERE slug = 'head-and-neck');

-- Remove "Lip" (standalone - now "Oral Cavity" covers this or it's "Lip and Oral Cavity")
DELETE FROM ajcc_disease_site 
WHERE slug = 'lip' 
AND body_section_id = (SELECT id FROM ajcc_body_section WHERE slug = 'head-and-neck');

-- Remove "Lip and Oral Cavity" (old name, now just "Oral Cavity")
DELETE FROM ajcc_disease_site 
WHERE slug = 'lip-and-oral-cavity' 
AND body_section_id = (SELECT id FROM ajcc_body_section WHERE slug = 'head-and-neck');

-- Remove old Oropharynx entries (keep only HPV-Associated and HPV-Independent versions)
DELETE FROM ajcc_disease_site 
WHERE slug IN ('oropharynx', 'oropharynx-p16-negative', 'hpv-mediated-p16-oropharyngeal-cancer')
AND body_section_id = (SELECT id FROM ajcc_body_section WHERE slug = 'head-and-neck');

-- Remove duplicate "Nasal Cavity and Paranasal Sinuses" with wrong slug
DELETE FROM ajcc_disease_site 
WHERE slug = 'nasal-cavity' 
AND body_section_id = (SELECT id FROM ajcc_body_section WHERE slug = 'head-and-neck');

-- Remove Major Salivary Glands (old name, now just "Salivary Glands")
DELETE FROM ajcc_disease_site 
WHERE slug = 'major-salivary-glands' 
AND body_section_id = (SELECT id FROM ajcc_body_section WHERE slug = 'head-and-neck');

-- Verify remaining entries
SELECT id, disease_name, slug, ajcc_url_path 
FROM ajcc_disease_site 
WHERE body_section_id = (SELECT id FROM ajcc_body_section WHERE slug = 'head-and-neck')
ORDER BY disease_name;
