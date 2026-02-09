-- Enable pg_trgm extension for fuzzy text matching (duplicate diagnosis detection)
-- Run on Neon: psql $DATABASE_URL -f migrations/enable_pg_trgm.sql

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- GIN index on diagnosis for fast similarity() / % queries
CREATE INDEX IF NOT EXISTS idx_case_diagnosis_trgm
    ON "case" USING GIN (diagnosis gin_trgm_ops);
