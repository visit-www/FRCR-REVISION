-- SQLite Migration: Make case_id nullable in candidate_note, text_highlight, forum_message
-- Purpose: Allow TNM-specific notes/highlights without a case association
-- Date: 2026-01-27
-- 
-- IMPORTANT: SQLite doesn't support ALTER COLUMN, so we must recreate tables.
-- This migration preserves all existing data.

-- ================================================
-- 1. Recreate candidate_note table
-- ================================================
PRAGMA foreign_keys=OFF;

-- Create new table with case_id nullable
CREATE TABLE candidate_note_new (
    id INTEGER NOT NULL PRIMARY KEY,
    case_id INTEGER,  -- NOW NULLABLE
    user_id INTEGER NOT NULL,
    note_text TEXT NOT NULL,
    created_at DATETIME,
    updated_at DATETIME,
    tnm_disease_id INTEGER,
    FOREIGN KEY(case_id) REFERENCES "case" (id),
    FOREIGN KEY(user_id) REFERENCES user (id),
    FOREIGN KEY(tnm_disease_id) REFERENCES ajcc_disease_site (id) ON DELETE SET NULL
);

-- Copy existing data
INSERT INTO candidate_note_new SELECT * FROM candidate_note;

-- Drop old table
DROP TABLE candidate_note;

-- Rename new table
ALTER TABLE candidate_note_new RENAME TO candidate_note;

-- Recreate indexes
CREATE INDEX ix_candidate_note_user_id ON candidate_note (user_id);
CREATE INDEX ix_candidate_note_case_id ON candidate_note (case_id);
CREATE INDEX idx_case_user ON candidate_note (case_id, user_id);
CREATE INDEX idx_tnm_user ON candidate_note (tnm_disease_id, user_id);

-- ================================================
-- 2. Recreate text_highlight table
-- ================================================
CREATE TABLE text_highlight_new (
    id INTEGER NOT NULL PRIMARY KEY,
    case_id INTEGER,  -- NOW NULLABLE
    user_id INTEGER NOT NULL,
    text_content TEXT NOT NULL,
    highlight_color VARCHAR(20) NOT NULL,
    field_name VARCHAR(50) NOT NULL,
    context_before VARCHAR(100),
    context_after VARCHAR(100),
    created_at DATETIME,
    tnm_disease_id INTEGER,
    FOREIGN KEY(case_id) REFERENCES "case" (id),
    FOREIGN KEY(user_id) REFERENCES user (id),
    FOREIGN KEY(tnm_disease_id) REFERENCES ajcc_disease_site (id) ON DELETE SET NULL
);

-- Copy existing data
INSERT INTO text_highlight_new SELECT * FROM text_highlight;

-- Drop old table
DROP TABLE text_highlight;

-- Rename new table
ALTER TABLE text_highlight_new RENAME TO text_highlight;

-- Recreate indexes
CREATE INDEX ix_text_highlight_user_id ON text_highlight (user_id);
CREATE INDEX ix_text_highlight_case_id ON text_highlight (case_id);
CREATE INDEX idx_case_user_highlight ON text_highlight (case_id, user_id);
CREATE INDEX idx_text_search ON text_highlight (text_content);
CREATE INDEX idx_tnm_user_highlight ON text_highlight (tnm_disease_id, user_id);

-- ================================================
-- 3. Recreate forum_message table
-- ================================================
CREATE TABLE forum_message_new (
    id INTEGER NOT NULL PRIMARY KEY,
    case_id INTEGER,  -- NOW NULLABLE
    user_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    vote_score INTEGER NOT NULL DEFAULT 0,
    is_pinned BOOLEAN DEFAULT 0,
    is_deleted BOOLEAN DEFAULT 0,
    flag_count INTEGER DEFAULT 0,
    image_url VARCHAR(500),
    image_public_id VARCHAR(255),
    image_thumbnail_url VARCHAR(500),
    created_at DATETIME,
    updated_at DATETIME,
    tnm_disease_id INTEGER,
    FOREIGN KEY(case_id) REFERENCES "case" (id),
    FOREIGN KEY(user_id) REFERENCES user (id),
    FOREIGN KEY(tnm_disease_id) REFERENCES ajcc_disease_site (id) ON DELETE SET NULL
);

-- Copy existing data
INSERT INTO forum_message_new SELECT * FROM forum_message;

-- Drop old table
DROP TABLE forum_message;

-- Rename new table
ALTER TABLE forum_message_new RENAME TO forum_message;

-- Recreate indexes
CREATE INDEX ix_forum_message_user_id ON forum_message (user_id);
CREATE INDEX ix_forum_message_case_id ON forum_message (case_id);
CREATE INDEX ix_forum_message_vote_score ON forum_message (vote_score);
CREATE INDEX ix_forum_message_is_pinned ON forum_message (is_pinned);
CREATE INDEX ix_forum_message_is_deleted ON forum_message (is_deleted);
CREATE INDEX ix_forum_message_flag_count ON forum_message (flag_count);
CREATE INDEX ix_forum_message_created_at ON forum_message (created_at);
CREATE INDEX idx_forum_case_votes ON forum_message (case_id, vote_score);
CREATE INDEX idx_forum_case_pinned ON forum_message (case_id, is_pinned);
CREATE INDEX idx_forum_flagged ON forum_message (flag_count);
CREATE INDEX idx_forum_tnm_disease ON forum_message (tnm_disease_id);

PRAGMA foreign_keys=ON;

-- Verify the changes
-- SELECT sql FROM sqlite_master WHERE name = 'candidate_note';
-- SELECT sql FROM sqlite_master WHERE name = 'text_highlight';
-- SELECT sql FROM sqlite_master WHERE name = 'forum_message';
