-- Migration: Add related_cases association table
-- Allows linking cases together (e.g., algorithm case → specific cancer cases)

-- For PostgreSQL (Neon)
CREATE TABLE IF NOT EXISTS related_cases (
    case_id INTEGER NOT NULL,
    related_case_id INTEGER NOT NULL,
    relation_type VARCHAR(50) DEFAULT 'related',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (case_id, related_case_id),
    FOREIGN KEY (case_id) REFERENCES "case" (id) ON DELETE CASCADE,
    FOREIGN KEY (related_case_id) REFERENCES "case" (id) ON DELETE CASCADE
);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_related_cases_case_id ON related_cases(case_id);
CREATE INDEX IF NOT EXISTS idx_related_cases_related_id ON related_cases(related_case_id);
