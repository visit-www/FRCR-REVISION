-- Add contributor_name column to case table for student attribution
-- Run on Neon: psql $DATABASE_URL -f migrations/add_contributor_name.sql

ALTER TABLE "case" ADD COLUMN IF NOT EXISTS contributor_name VARCHAR(120);
