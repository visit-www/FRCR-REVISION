-- Add study_label to case_image_stack
-- Add stack_id to case_image_annotation

ALTER TABLE case_image_stack ADD COLUMN IF NOT EXISTS study_label VARCHAR(200);

ALTER TABLE case_image_annotation ADD COLUMN IF NOT EXISTS stack_id INTEGER REFERENCES case_image_stack(id) ON DELETE CASCADE;

ALTER TABLE case_image_annotation DROP CONSTRAINT IF EXISTS case_image_annotation_case_id_key;

CREATE UNIQUE INDEX IF NOT EXISTS ix_case_image_annotation_stack_id ON case_image_annotation(stack_id) WHERE stack_id IS NOT NULL;
