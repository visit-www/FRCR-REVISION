-- Add calculator_slug column to case table
-- This allows admins to optionally assign a calculator to a case
-- e.g., 'oropharynx', 'lung', 'breast', etc.

-- SQLite version
ALTER TABLE "case" ADD COLUMN calculator_slug VARCHAR(50);

-- PostgreSQL version (for Neon)
-- ALTER TABLE "case" ADD COLUMN IF NOT EXISTS calculator_slug VARCHAR(50);
