-- Add study_label to case_image_stack (Study = CaseImageStack in UI)
-- Add stack_id to case_image_annotation (annotations per-study)
-- Run on Neon/PostgreSQL via: python scripts/utilities/run_sql_migration_vercel_only.py migrations/add_study_label_and_annotation_stack_id.sql

-- case_image_stack: study_label (nullable for existing rows; new R2 stacks require it)
ALTER TABLE case_image_stack ADD COLUMN IF NOT EXISTS study_label VARCHAR(200);

-- case_image_annotation: add stack_id for per-study annotations
ALTER TABLE case_image_annotation ADD COLUMN IF NOT EXISTS stack_id INTEGER REFERENCES case_image_stack(id) ON DELETE CASCADE;

-- Allow multiple annotation rows (one per stack); drop unique on case_id if exists
ALTER TABLE case_image_annotation DROP CONSTRAINT IF EXISTS case_image_annotation_case_id_key;

-- Unique on stack_id (one annotation record per study)
CREATE UNIQUE INDEX IF NOT EXISTS ix_case_image_annotation_stack_id ON case_image_annotation(stack_id) WHERE stack_id IS NOT NULL;
