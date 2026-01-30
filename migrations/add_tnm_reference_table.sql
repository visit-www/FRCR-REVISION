-- Migration: Add tnm_reference table
-- Date: 2026-01-30
-- Description: Creates the tnm_reference table to store references for TNM disease sites,
--              mirroring the structure of case_reference table.

-- ============================================================================
-- CREATE TNM_REFERENCE TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS tnm_reference (
    id SERIAL PRIMARY KEY,
    disease_site_id INTEGER NOT NULL REFERENCES ajcc_disease_site(id) ON DELETE CASCADE,
    
    -- Reference data
    ref_number INTEGER NOT NULL,      -- The [1], [2], etc. display number
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    journal VARCHAR(500),
    year VARCHAR(10),
    
    -- Whether this reference has an inline citation (superscript) in the content
    -- False = added via search/manual (reference list only, hidden superscript)
    -- True = added via context menu (has visible [N] superscript in text)
    is_inline BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Index on disease_site_id for efficient lookups
CREATE INDEX IF NOT EXISTS idx_tnm_reference_disease_site_id ON tnm_reference(disease_site_id);

-- ============================================================================
-- UNIQUE CONSTRAINTS
-- ============================================================================

-- One ref_number per disease site
ALTER TABLE tnm_reference
ADD CONSTRAINT uq_tnm_ref_number UNIQUE (disease_site_id, ref_number);

-- One URL per disease site (prevent duplicates)
ALTER TABLE tnm_reference
ADD CONSTRAINT uq_tnm_ref_url UNIQUE (disease_site_id, url);

-- ============================================================================
-- VERIFICATION
-- ============================================================================

-- Verify table was created
SELECT 'tnm_reference table created successfully' AS status
WHERE EXISTS (
    SELECT FROM information_schema.tables 
    WHERE table_name = 'tnm_reference'
);

-- Show table structure
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'tnm_reference'
ORDER BY ordinal_position;
