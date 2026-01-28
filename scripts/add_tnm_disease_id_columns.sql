-- Migration: Add tnm_disease_id columns to CandidateNote, TextHighlight, and ForumMessage
-- Run this on the production database (Neon) to fix the missing column error
-- Date: 2026-01-28

-- Step 1: Add tnm_disease_id to candidate_note table
ALTER TABLE candidate_note 
ADD COLUMN IF NOT EXISTS tnm_disease_id INTEGER REFERENCES ajcc_disease_site(id);

-- Step 2: Create index for efficient lookups
CREATE INDEX IF NOT EXISTS idx_candidate_note_tnm_user 
ON candidate_note(tnm_disease_id, user_id);

-- Step 3: Add tnm_disease_id to text_highlight table (if not exists)
ALTER TABLE text_highlight 
ADD COLUMN IF NOT EXISTS tnm_disease_id INTEGER REFERENCES ajcc_disease_site(id);

-- Step 4: Create index for text_highlight
CREATE INDEX IF NOT EXISTS idx_text_highlight_tnm_user 
ON text_highlight(tnm_disease_id, user_id);

-- Step 5: Add tnm_disease_id to forum_message table (if not exists)
ALTER TABLE forum_message 
ADD COLUMN IF NOT EXISTS tnm_disease_id INTEGER REFERENCES ajcc_disease_site(id);

-- Step 6: Create index for forum_message
CREATE INDEX IF NOT EXISTS idx_forum_message_tnm_disease 
ON forum_message(tnm_disease_id);

-- Verify the columns were added
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name IN ('candidate_note', 'text_highlight', 'forum_message') 
  AND column_name = 'tnm_disease_id';
