-- Migration: Allow multiple image stacks per case, add display_order
-- Date: 2026-02-03

-- Add display_order (0 = first)
ALTER TABLE case_image_stack
ADD COLUMN IF NOT EXISTS display_order INTEGER DEFAULT 0;

-- Drop unique constraint on case_id (PostgreSQL: try common names)
DROP INDEX IF EXISTS ix_case_image_stack_case_id;
DROP INDEX IF EXISTS uq_case_image_stack_case_id;
ALTER TABLE case_image_stack DROP CONSTRAINT IF EXISTS case_image_stack_case_id_key;

-- Create non-unique index for efficient lookups
CREATE INDEX IF NOT EXISTS ix_case_image_stack_case_id ON case_image_stack(case_id);

COMMENT ON COLUMN case_image_stack.display_order IS 'Order when multiple stacks per case (0 = first)';
