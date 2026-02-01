-- Migration: Add case_reference_image table for CC-licensed reference images
-- Run this on Vercel PostgreSQL / Neon database
-- Date: 2026-01-31

-- Create case_reference_image table
CREATE TABLE IF NOT EXISTS case_reference_image (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES "case"(id) ON DELETE CASCADE,
    source_url VARCHAR(1000) NOT NULL,
    source_domain VARCHAR(255) NOT NULL,
    thumbnail_url VARCHAR(500),
    image_type VARCHAR(50) NOT NULL DEFAULT 'ct_mri',
    modality VARCHAR(50),
    ai_description TEXT,
    ai_relevance_score REAL,
    admin_note TEXT,
    display_order INTEGER DEFAULT 0,
    added_by_user_id INTEGER REFERENCES "user"(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    license VARCHAR(100) NOT NULL DEFAULT 'CC BY 4.0',
    attribution VARCHAR(500) NOT NULL
);

-- Create index
CREATE INDEX IF NOT EXISTS ix_case_reference_image_case_id ON case_reference_image(case_id);

-- Add comment
COMMENT ON TABLE case_reference_image IS 'Admin-curated CC-licensed reference images for cases (CT/MRI, anatomy diagrams, concept diagrams). Displayed in Anatomy tab.';
