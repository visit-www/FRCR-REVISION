-- Migration: Add contributor_notes column to case table
-- Date: 2026-02-08
-- Purpose: Student "Additional Insights" text for Suggest a Case feature
-- Note: Column is nullable, no default needed. ALTER TABLE required on Neon.

ALTER TABLE "case" ADD COLUMN IF NOT EXISTS contributor_notes TEXT;
