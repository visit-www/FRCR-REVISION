-- Migration: Add tnm_disease_id to CandidateNote, TextHighlight, and ForumMessage tables
-- Purpose: Allow notes, highlights, and forum messages to be associated with TNM disease sites
-- Date: 2026-01-27

-- ================================================
-- Add tnm_disease_id column to candidate_note table
-- ================================================
ALTER TABLE candidate_note 
ADD COLUMN IF NOT EXISTS tnm_disease_id INTEGER REFERENCES ajcc_disease_site(id) ON DELETE SET NULL;

-- Create index for TNM-specific note lookups
CREATE INDEX IF NOT EXISTS idx_note_tnm_disease 
ON candidate_note(tnm_disease_id, user_id) 
WHERE tnm_disease_id IS NOT NULL;

-- ================================================
-- Add tnm_disease_id column to text_highlight table
-- ================================================
ALTER TABLE text_highlight 
ADD COLUMN IF NOT EXISTS tnm_disease_id INTEGER REFERENCES ajcc_disease_site(id) ON DELETE SET NULL;

-- Create index for TNM-specific highlight lookups
CREATE INDEX IF NOT EXISTS idx_highlight_tnm_disease 
ON text_highlight(tnm_disease_id, user_id) 
WHERE tnm_disease_id IS NOT NULL;

-- ================================================
-- Add tnm_disease_id column to forum_message table
-- ================================================
ALTER TABLE forum_message 
ADD COLUMN IF NOT EXISTS tnm_disease_id INTEGER REFERENCES ajcc_disease_site(id) ON DELETE SET NULL;

-- Create index for TNM-specific forum message lookups
CREATE INDEX IF NOT EXISTS idx_forum_tnm_disease 
ON forum_message(tnm_disease_id) 
WHERE tnm_disease_id IS NOT NULL;

-- ================================================
-- Verification Query (run after migration)
-- ================================================
-- SELECT 
--     'candidate_note' as table_name, 
--     column_name, 
--     data_type 
-- FROM information_schema.columns 
-- WHERE table_name = 'candidate_note' AND column_name = 'tnm_disease_id'
-- UNION ALL
-- SELECT 
--     'text_highlight' as table_name, 
--     column_name, 
--     data_type 
-- FROM information_schema.columns 
-- WHERE table_name = 'text_highlight' AND column_name = 'tnm_disease_id'
-- UNION ALL
-- SELECT 
--     'forum_message' as table_name, 
--     column_name, 
--     data_type 
-- FROM information_schema.columns 
-- WHERE table_name = 'forum_message' AND column_name = 'tnm_disease_id';
