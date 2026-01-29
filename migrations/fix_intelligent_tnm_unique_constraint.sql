-- Migration: Fix IntelligentTNMData unique constraint
-- Problem: The constraint on (disease_site_id, diagnosis_year_id) allows NULL duplicates
--          because NULL != NULL in SQL. This causes duplicate records.
-- Solution: Change to unique constraint on disease_site_id only (one record per disease site)
--
-- EXECUTED: 2026-01-29 on Neon production database
-- Status: COMPLETE

BEGIN;

-- Step 1: Identify and delete duplicate records, keeping only the most recently updated one
-- First, let's see what duplicates exist
SELECT disease_site_id, COUNT(*) as count 
FROM intelligent_tnm_data 
GROUP BY disease_site_id 
HAVING COUNT(*) > 1;

-- Delete duplicates, keeping the record with the most recent updated_at timestamp
-- Using a subquery to find the ID of the most recently updated record per disease_site_id
DELETE FROM intelligent_tnm_data 
WHERE id NOT IN (
    SELECT DISTINCT ON (disease_site_id) id
    FROM intelligent_tnm_data 
    ORDER BY disease_site_id, updated_at DESC NULLS LAST, id DESC
);

-- Step 2: Drop the old constraint (handles NULL duplicates poorly)
ALTER TABLE intelligent_tnm_data 
DROP CONSTRAINT IF EXISTS uq_disease_year_intelligence;

-- Step 3: Add new unique constraint on disease_site_id only
-- This ensures exactly one intelligence record per disease site
ALTER TABLE intelligent_tnm_data 
ADD CONSTRAINT uq_disease_site_intelligence UNIQUE (disease_site_id);

-- Step 4: Update the index to match (optional - for query efficiency)
DROP INDEX IF EXISTS idx_disease_intelligence;
CREATE INDEX idx_disease_intelligence ON intelligent_tnm_data (disease_site_id);

-- Verify the constraint
SELECT 
    tc.constraint_name, 
    kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu 
    ON tc.constraint_name = kcu.constraint_name
WHERE tc.table_name = 'intelligent_tnm_data' 
    AND tc.constraint_type = 'UNIQUE';

COMMIT;

-- Expected output after running:
-- uq_disease_site_intelligence | disease_site_id
