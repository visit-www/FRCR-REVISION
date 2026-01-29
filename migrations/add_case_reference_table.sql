-- Migration: Add CaseReference table
-- Purpose: Store case references in a proper database table instead of embedded HTML
-- 
-- Run this migration on the Neon database before deploying the new code

BEGIN;

-- Create the case_reference table
CREATE TABLE IF NOT EXISTS case_reference (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES "case"(id) ON DELETE CASCADE,
    ref_number INTEGER NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    journal VARCHAR(500),
    year VARCHAR(10),
    is_inline BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Unique constraints
    CONSTRAINT uq_case_ref_number UNIQUE (case_id, ref_number),
    CONSTRAINT uq_case_ref_url UNIQUE (case_id, url)
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_case_reference_case_id ON case_reference(case_id);

-- Verify the table was created
SELECT 'case_reference table created successfully' AS status;

COMMIT;
