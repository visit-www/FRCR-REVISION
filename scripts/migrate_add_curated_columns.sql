-- Migration: Add curated columns to ajcc_staging_data table
-- Run this on Neon database to fix the 500 error

-- Add curated content columns
ALTER TABLE ajcc_staging_data 
ADD COLUMN IF NOT EXISTS curated_quick_reference_html TEXT;

ALTER TABLE ajcc_staging_data 
ADD COLUMN IF NOT EXISTS curated_explanatory_notes_html TEXT;

-- Add curation status columns
ALTER TABLE ajcc_staging_data 
ADD COLUMN IF NOT EXISTS is_curated BOOLEAN DEFAULT FALSE;

ALTER TABLE ajcc_staging_data 
ADD COLUMN IF NOT EXISTS curated_by_user_id INTEGER REFERENCES "user"(id);

ALTER TABLE ajcc_staging_data 
ADD COLUMN IF NOT EXISTS curated_at TIMESTAMP;

-- Create index for is_curated (for efficient queries)
CREATE INDEX IF NOT EXISTS idx_ajcc_staging_is_curated ON ajcc_staging_data(is_curated);

-- Verify columns were added
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'ajcc_staging_data' 
AND column_name LIKE 'curated%' OR column_name = 'is_curated';
