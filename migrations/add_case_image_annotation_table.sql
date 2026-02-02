-- Migration: Add case_image_annotation table for storing admin annotations on image stacks
-- Date: 2026-02-02

-- Create the case_image_annotation table
CREATE TABLE IF NOT EXISTS case_image_annotation (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL UNIQUE REFERENCES "case"(id) ON DELETE CASCADE,
    annotations_json TEXT NOT NULL DEFAULT '{}',
    created_by_user_id INTEGER REFERENCES "user"(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_case_image_annotation_case_id ON case_image_annotation(case_id);

-- Comment
COMMENT ON TABLE case_image_annotation IS 'Stores Cornerstone.js annotations (arrows, text, measurements) for case image stacks';
COMMENT ON COLUMN case_image_annotation.annotations_json IS 'JSON format: { planName: { imageIndex: [{ toolType, data }] } }';
