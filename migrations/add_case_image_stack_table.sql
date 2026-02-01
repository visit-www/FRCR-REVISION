-- Migration: Add case_image_stack table for OneDrive-linked DICOM-like image stacks
-- Run this on Vercel PostgreSQL / Neon database
-- Date: 2026-01-31

CREATE TABLE IF NOT EXISTS case_image_stack (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL UNIQUE REFERENCES "case"(id) ON DELETE CASCADE,
    onedrive_share_id VARCHAR(500) NOT NULL,
    onedrive_folder_path VARCHAR(500),
    config_json TEXT NOT NULL,
    created_by_user_id INTEGER REFERENCES "user"(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_case_image_stack_case_id ON case_image_stack(case_id);

COMMENT ON TABLE case_image_stack IS 'OneDrive-linked image stacks for cases (axial, sagittal, etc.). DICOM-like viewer.';
