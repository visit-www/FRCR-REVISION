-- Migration: Add user_qa_progress table for SM-2 spaced repetition study system
-- Date: 2026-02-08
-- Note: Table is auto-created by db.create_all() on Neon. This SQL is a backup.

CREATE TABLE IF NOT EXISTS user_qa_progress (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    question_id INTEGER NOT NULL REFERENCES question(id) ON DELETE CASCADE,
    case_id INTEGER NOT NULL REFERENCES "case"(id) ON DELETE CASCADE,
    ease_factor FLOAT NOT NULL DEFAULT 2.5,
    interval_days INTEGER NOT NULL DEFAULT 0,
    repetition_number INTEGER NOT NULL DEFAULT 0,
    next_review_date DATE NOT NULL,
    last_reviewed_at TIMESTAMP,
    times_correct INTEGER NOT NULL DEFAULT 0,
    times_incorrect INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_question_progress UNIQUE (user_id, question_id)
);

CREATE INDEX IF NOT EXISTS idx_user_qa_progress_user_id ON user_qa_progress(user_id);
CREATE INDEX IF NOT EXISTS idx_user_qa_progress_question_id ON user_qa_progress(question_id);
CREATE INDEX IF NOT EXISTS idx_user_qa_progress_case_id ON user_qa_progress(case_id);
CREATE INDEX IF NOT EXISTS idx_user_qa_progress_next_review ON user_qa_progress(next_review_date);
CREATE INDEX IF NOT EXISTS idx_user_qa_due ON user_qa_progress(user_id, next_review_date);
