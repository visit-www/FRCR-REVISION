-- Migration: Add onedrive_refresh_token_encrypted to case_image_stack for server-side URL refresh
-- Date: 2026-02-02

ALTER TABLE case_image_stack
ADD COLUMN IF NOT EXISTS onedrive_refresh_token_encrypted TEXT;

COMMENT ON COLUMN case_image_stack.onedrive_refresh_token_encrypted IS 'Encrypted OneDrive refresh token for server-side URL refresh (all viewers get fresh URLs)';
