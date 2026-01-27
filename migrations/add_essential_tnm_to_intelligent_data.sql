-- Migration: Add essential_tnm_json to IntelligentTNMData table
-- This stores cancer-specific Essential TNM concepts from IARC for the 7 applicable cancers
-- (breast, colorectal, ovarian, cervical, prostate, lymphoma, liver)

-- PostgreSQL (Vercel Neon)
ALTER TABLE intelligent_tnm_data 
ADD COLUMN IF NOT EXISTS essential_tnm_json TEXT;

-- SQLite (local development)
-- Note: SQLite doesn't support IF NOT EXISTS for ADD COLUMN
-- Run this separately if column doesn't exist:
-- ALTER TABLE intelligent_tnm_data ADD COLUMN essential_tnm_json TEXT;

-- Add comment (PostgreSQL only)
COMMENT ON COLUMN intelligent_tnm_data.essential_tnm_json IS 
'JSON object with cancer-specific IARC Essential TNM content. Contains: cancer_type, figure_url, key_concepts, attribution. Only for 7 cancers.';
