-- Add calculator_slug column to case table
-- This allows admins to optionally assign a calculator to a case
-- e.g., 'oropharynx', 'lung', 'breast', etc.

-- PostgreSQL version (for Neon) - use IF NOT EXISTS
ALTER TABLE "case" ADD COLUMN IF NOT EXISTS calculator_slug VARCHAR(50);
