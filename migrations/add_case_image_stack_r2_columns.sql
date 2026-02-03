-- Migration: Add storage_backend and r2_config_json to case_image_stack for R2 migration
-- Date: 2026-02-03

ALTER TABLE case_image_stack
ADD COLUMN IF NOT EXISTS storage_backend VARCHAR(20) DEFAULT 'onedrive';

ALTER TABLE case_image_stack
ADD COLUMN IF NOT EXISTS r2_config_json JSONB;

-- Allow onedrive_share_id to be NULL for R2-only stacks
ALTER TABLE case_image_stack
ALTER COLUMN onedrive_share_id DROP NOT NULL;

COMMENT ON COLUMN case_image_stack.storage_backend IS 'Storage backend: onedrive (legacy) or r2';
COMMENT ON COLUMN case_image_stack.r2_config_json IS 'R2 object keys per plan: {"axial": ["key1", "key2"], "sagittal": [...]}';
