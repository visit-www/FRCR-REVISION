-- Migration: Add essential_tnm_json column to intelligent_tnm_data
-- This column stores IARC Essential TNM key concepts for applicable cancers
--
-- EXECUTED: 2026-01-29 on Neon production database
-- Status: COMPLETE

-- Add the essential_tnm_json column if it doesn't exist
ALTER TABLE intelligent_tnm_data 
ADD COLUMN IF NOT EXISTS essential_tnm_json TEXT;

-- The column stores JSON with structure:
-- {
--   "figure_url": "cloudinary URL",
--   "title": "Cancer Title",
--   "key_concepts": ["concept 1", "concept 2", ...],
--   "supplementary_table": "HTML table content",
--   "attribution": "IARC Essential TNM Guide (CC BY-NC-ND 3.0 IGO)"
-- }
