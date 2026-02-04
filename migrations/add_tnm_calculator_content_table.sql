-- Migration: Add TNM Calculator Content table
-- Stores AI-generated TNM calculator HTML and algorithm content

-- For SQLite
CREATE TABLE IF NOT EXISTS tnm_calculator_content (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug VARCHAR(100) UNIQUE NOT NULL,
    cancer_name VARCHAR(200) NOT NULL,
    body_section VARCHAR(100) NOT NULL,
    calculator_html TEXT,
    algorithm_discussion_html TEXT,
    staging_system VARCHAR(50) DEFAULT 'AJCC 9th Edition',
    special_features TEXT,
    description VARCHAR(500),
    is_available BOOLEAN DEFAULT 0 NOT NULL,
    generation_prompt TEXT,
    generation_model VARCHAR(100),
    generated_at TIMESTAMP,
    algorithm_case_id INTEGER REFERENCES "case" (id),
    created_by_user_id INTEGER REFERENCES "user" (id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_tnm_calc_slug ON tnm_calculator_content (slug);
CREATE INDEX IF NOT EXISTS idx_tnm_calc_algorithm_case ON tnm_calculator_content (algorithm_case_id);

-- For PostgreSQL (Neon) - run this version if SQLite fails
-- CREATE TABLE IF NOT EXISTS tnm_calculator_content (
--     id SERIAL PRIMARY KEY,
--     slug VARCHAR(100) UNIQUE NOT NULL,
--     cancer_name VARCHAR(200) NOT NULL,
--     body_section VARCHAR(100) NOT NULL,
--     calculator_html TEXT,
--     algorithm_discussion_html TEXT,
--     staging_system VARCHAR(50) DEFAULT 'AJCC 9th Edition',
--     special_features TEXT,
--     description VARCHAR(500),
--     is_available BOOLEAN DEFAULT FALSE NOT NULL,
--     generation_prompt TEXT,
--     generation_model VARCHAR(100),
--     generated_at TIMESTAMP,
--     algorithm_case_id INTEGER REFERENCES "case" (id),
--     created_by_user_id INTEGER REFERENCES "user" (id),
--     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--     updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
-- );
--
-- CREATE INDEX IF NOT EXISTS idx_tnm_calc_slug ON tnm_calculator_content (slug);
-- CREATE INDEX IF NOT EXISTS idx_tnm_calc_algorithm_case ON tnm_calculator_content (algorithm_case_id);
