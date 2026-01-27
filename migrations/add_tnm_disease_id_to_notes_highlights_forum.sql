-- Migration: Add tnm_disease_id to CandidateNote, TextHighlight, and ForumMessage tables
-- Purpose: Allow notes, highlights, and forum messages to be associated with TNM disease sites
-- Date: 2026-01-27

-- ================================================
-- IMPORTANT: SQLite does not support ALTER COLUMN to change NULL constraints.
-- We need to recreate the tables to make case_id nullable.
-- This migration handles both PostgreSQL and SQLite approaches.
-- ================================================

-- ================================================
-- PostgreSQL: Alter case_id to be nullable and add tnm_disease_id
-- ================================================
-- For PostgreSQL (Vercel Neon), run these commands:

-- ALTER TABLE candidate_note ALTER COLUMN case_id DROP NOT NULL;
-- ALTER TABLE candidate_note ADD COLUMN IF NOT EXISTS tnm_disease_id INTEGER REFERENCES ajcc_disease_site(id) ON DELETE SET NULL;
-- CREATE INDEX IF NOT EXISTS idx_note_tnm_disease ON candidate_note(tnm_disease_id, user_id) WHERE tnm_disease_id IS NOT NULL;

-- ALTER TABLE text_highlight ALTER COLUMN case_id DROP NOT NULL;
-- ALTER TABLE text_highlight ADD COLUMN IF NOT EXISTS tnm_disease_id INTEGER REFERENCES ajcc_disease_site(id) ON DELETE SET NULL;
-- CREATE INDEX IF NOT EXISTS idx_highlight_tnm_disease ON text_highlight(tnm_disease_id, user_id) WHERE tnm_disease_id IS NOT NULL;

-- ALTER TABLE forum_message ALTER COLUMN case_id DROP NOT NULL;
-- ALTER TABLE forum_message ADD COLUMN IF NOT EXISTS tnm_disease_id INTEGER REFERENCES ajcc_disease_site(id) ON DELETE SET NULL;
-- CREATE INDEX IF NOT EXISTS idx_forum_tnm_disease ON forum_message(tnm_disease_id) WHERE tnm_disease_id IS NOT NULL;

-- ================================================
-- SQLite: Recreate tables to change case_id constraint
-- ================================================
-- SQLite requires table recreation to change NOT NULL constraint.
-- Run the SQLite-specific migration in migrations/sqlite_make_case_id_nullable.sql

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
