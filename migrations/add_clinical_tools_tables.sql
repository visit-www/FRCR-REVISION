-- Migration: Add clinical tools tables (On-Call Helper, Reporting Templates, Incidental Findings)
-- Run on Neon: psql $DATABASE_URL -f migrations/add_clinical_tools_tables.sql

-- ==================== CLINICAL PROTOCOL (On-Call Helper Knowledge Base) ====================
CREATE TABLE IF NOT EXISTS clinical_protocol (
    id SERIAL PRIMARY KEY,
    category VARCHAR(50) NOT NULL,
    title VARCHAR(300) NOT NULL,
    keywords TEXT NOT NULL,
    content_structured TEXT,
    content_html TEXT,
    source_citation VARCHAR(500) NOT NULL,
    guideline_version VARCHAR(100),
    source_url VARCHAR(1000),
    is_published BOOLEAN NOT NULL DEFAULT FALSE,
    verified_by_user_id INTEGER REFERENCES "user"(id),
    verified_at TIMESTAMP,
    created_by_user_id INTEGER REFERENCES "user"(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- pg_trgm indexes for fuzzy search on protocols
CREATE INDEX IF NOT EXISTS idx_clinical_protocol_category
    ON clinical_protocol (category);
CREATE INDEX IF NOT EXISTS idx_clinical_protocol_published
    ON clinical_protocol (is_published);
CREATE INDEX IF NOT EXISTS idx_clinical_protocol_keywords_trgm
    ON clinical_protocol USING GIN (keywords gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_clinical_protocol_title_trgm
    ON clinical_protocol USING GIN (title gin_trgm_ops);

-- ==================== ON-CALL QUERY LOG (Audit Trail) ====================
CREATE TABLE IF NOT EXISTS oncall_query_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES "user"(id),
    query_text TEXT NOT NULL,
    matched_protocol_ids TEXT,
    ai_response_text TEXT,
    model_used VARCHAR(100),
    token_count INTEGER,
    response_source VARCHAR(50) DEFAULT 'protocol',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_oncall_query_log_user
    ON oncall_query_log (user_id);
CREATE INDEX IF NOT EXISTS idx_oncall_query_log_created
    ON oncall_query_log (created_at);

-- ==================== REPORTING TEMPLATE (Non-Oncologic Decision Trees) ====================
CREATE TABLE IF NOT EXISTS reporting_template (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(200) UNIQUE NOT NULL,
    title VARCHAR(300) NOT NULL,
    category VARCHAR(100) NOT NULL,
    body_section VARCHAR(100),
    description VARCHAR(500),
    keywords TEXT,
    template_html TEXT,
    algorithm_html TEXT,
    source_citation VARCHAR(500),
    guideline_version VARCHAR(100),
    is_available BOOLEAN NOT NULL DEFAULT FALSE,
    generation_prompt TEXT,
    generation_model VARCHAR(100),
    generated_at TIMESTAMP,
    created_by_user_id INTEGER REFERENCES "user"(id),
    last_edit_note VARCHAR(500),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reporting_template_slug
    ON reporting_template (slug);
CREATE INDEX IF NOT EXISTS idx_reporting_template_category
    ON reporting_template (category);
CREATE INDEX IF NOT EXISTS idx_reporting_template_available
    ON reporting_template (is_available);
CREATE INDEX IF NOT EXISTS idx_reporting_template_keywords_trgm
    ON reporting_template USING GIN (keywords gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_reporting_template_title_trgm
    ON reporting_template USING GIN (title gin_trgm_ops);

-- ==================== INCIDENTAL FINDING CALCULATOR ====================
CREATE TABLE IF NOT EXISTS incidental_finding_calculator (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(200) UNIQUE NOT NULL,
    finding_name VARCHAR(300) NOT NULL,
    body_section VARCHAR(100),
    category VARCHAR(100),
    description VARCHAR(500),
    keywords TEXT,
    calculator_html TEXT,
    algorithm_html TEXT,
    guideline_source VARCHAR(300),
    guideline_version VARCHAR(100),
    guideline_url VARCHAR(1000),
    is_available BOOLEAN NOT NULL DEFAULT FALSE,
    generation_prompt TEXT,
    generation_model VARCHAR(100),
    generated_at TIMESTAMP,
    verified_by_user_id INTEGER REFERENCES "user"(id),
    verified_at TIMESTAMP,
    created_by_user_id INTEGER REFERENCES "user"(id),
    last_edit_note VARCHAR(500),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_if_calculator_slug
    ON incidental_finding_calculator (slug);
CREATE INDEX IF NOT EXISTS idx_if_calculator_category
    ON incidental_finding_calculator (category);
CREATE INDEX IF NOT EXISTS idx_if_calculator_available
    ON incidental_finding_calculator (is_available);
CREATE INDEX IF NOT EXISTS idx_if_calculator_keywords_trgm
    ON incidental_finding_calculator USING GIN (keywords gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_if_calculator_name_trgm
    ON incidental_finding_calculator USING GIN (finding_name gin_trgm_ops);
