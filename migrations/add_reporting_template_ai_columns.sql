-- Migration: Add AI generation + caching columns to reporting_template
-- Run on Neon: psql $DATABASE_URL -f migrations/add_reporting_template_ai_columns.sql

-- New columns for AI-generated algorithm caching
ALTER TABLE reporting_template ADD COLUMN IF NOT EXISTS is_ai_generated BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE reporting_template ADD COLUMN IF NOT EXISTS verified_by_user_id INTEGER REFERENCES "user"(id);
ALTER TABLE reporting_template ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP;
ALTER TABLE reporting_template ADD COLUMN IF NOT EXISTS pacs_report_text TEXT;
