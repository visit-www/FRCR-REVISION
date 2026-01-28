-- Migration: Add TNMImage table for disease-linked images
-- Run this on Vercel PostgreSQL database
-- Date: 2025-01-28

-- Create tnm_image table
CREATE TABLE IF NOT EXISTS tnm_image (
    id SERIAL PRIMARY KEY,
    disease_site_id INTEGER NOT NULL REFERENCES ajcc_disease_site(id),
    diagnosis_year_id INTEGER REFERENCES ajcc_diagnosis_year(id),
    title VARCHAR(300),
    description TEXT,
    alt_text VARCHAR(500),
    cloudinary_url VARCHAR(500) NOT NULL,
    cloudinary_public_id VARCHAR(300) NOT NULL,
    width INTEGER,
    height INTEGER,
    image_type VARCHAR(50) DEFAULT 'reference',
    uploaded_by_user_id INTEGER REFERENCES "user"(id),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_tnm_image_disease_site ON tnm_image(disease_site_id);
CREATE INDEX IF NOT EXISTS idx_tnm_image_diagnosis_year ON tnm_image(diagnosis_year_id);
CREATE INDEX IF NOT EXISTS idx_tnm_image_disease ON tnm_image(disease_site_id, is_active);

-- Add comment
COMMENT ON TABLE tnm_image IS 'Stores images uploaded for TNM disease sites with Cloudinary URLs';
