-- Make onedrive_share_id nullable for R2-only stacks (Neon/PostgreSQL)
-- Run after add_case_image_stack_r2_columns.sql
-- If column is already nullable, this may error - safe to ignore
ALTER TABLE case_image_stack ALTER COLUMN onedrive_share_id DROP NOT NULL;
