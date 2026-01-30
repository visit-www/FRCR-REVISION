-- Migration: Add display_order column to ajcc_disease_site
-- Purpose: Enable custom ordering of disease sites within sections
-- Date: 2026-01-30

-- Add display_order column if it doesn't exist
ALTER TABLE ajcc_disease_site 
ADD COLUMN IF NOT EXISTS display_order INTEGER DEFAULT 0;

-- ============================================================
-- HEAD AND NECK SECTION - Custom Order
-- ============================================================
-- Order specified by product owner:
-- 1. Staging Principles of Head and Neck Cancers
-- 2. Cervical Lymph Nodes and Unknown Primary
-- 3. Nasopharynx
-- 4. Oropharynx (HPV-Associated)
-- 5. Oropharynx (HPV-Independent) and Hypopharynx
-- 6. Oral Cavity
-- 7. Larynx
-- 8. Nasal Cavity and Paranasal Sinuses
-- 9. Salivary Glands
-- 10. Cutaneous Carcinoma of the Head and Neck
-- 11. Mucosal Melanoma of the Head and Neck

UPDATE ajcc_disease_site SET display_order = 1 WHERE id = 92;  -- Staging Principles
UPDATE ajcc_disease_site SET display_order = 2 WHERE id = 98;  -- Cervical Lymph Nodes
UPDATE ajcc_disease_site SET display_order = 3 WHERE id = 4;   -- Nasopharynx
UPDATE ajcc_disease_site SET display_order = 4 WHERE id = 93;  -- Oropharynx (HPV+)
UPDATE ajcc_disease_site SET display_order = 5 WHERE id = 94;  -- Oropharynx (HPV-) and Hypopharynx
UPDATE ajcc_disease_site SET display_order = 6 WHERE id = 2;   -- Oral Cavity
UPDATE ajcc_disease_site SET display_order = 7 WHERE id = 1;   -- Larynx
UPDATE ajcc_disease_site SET display_order = 8 WHERE id = 95;  -- Nasal Cavity and Paranasal Sinuses
UPDATE ajcc_disease_site SET display_order = 9 WHERE id = 26;  -- Salivary Glands
UPDATE ajcc_disease_site SET display_order = 10 WHERE id = 97; -- Cutaneous Carcinoma
UPDATE ajcc_disease_site SET display_order = 11 WHERE id = 96; -- Mucosal Melanoma

-- ============================================================
-- VERIFICATION
-- ============================================================
-- SELECT id, disease_name, display_order 
-- FROM ajcc_disease_site 
-- WHERE body_section_id = 1 
-- ORDER BY display_order;
