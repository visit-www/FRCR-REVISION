-- Migration: Add overwrite column to tnm_generator_job table
-- Purpose: Allow regeneration of existing TNM calculators

-- PostgreSQL (Neon)
ALTER TABLE tnm_generator_job ADD COLUMN IF NOT EXISTS overwrite BOOLEAN DEFAULT FALSE;

-- SQLite version (run separately if needed):
-- ALTER TABLE tnm_generator_job ADD COLUMN overwrite INTEGER DEFAULT 0;
