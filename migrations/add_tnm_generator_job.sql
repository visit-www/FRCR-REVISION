-- Migration: Add TNM Generator Job Queue table
-- Purpose: Enable async generation with cron processing (Vercel Hobby workaround)

CREATE TABLE IF NOT EXISTS tnm_generator_job (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(36) UNIQUE NOT NULL,

    -- Job parameters
    slug VARCHAR(100) NOT NULL,
    cancer_name VARCHAR(200) NOT NULL,
    body_section VARCHAR(100) NOT NULL,
    staging_system VARCHAR(50) DEFAULT 'AJCC 9th Edition',
    description VARCHAR(500),
    special_features TEXT,
    special_notes TEXT,

    -- Status: pending, running, completed, failed
    status VARCHAR(20) DEFAULT 'pending' NOT NULL,
    error_message TEXT,

    -- Timing
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,

    -- User who requested
    created_by_user_id INTEGER REFERENCES "user"(id)
);

-- Index for fast pending job lookup
CREATE INDEX IF NOT EXISTS idx_tnm_generator_job_status ON tnm_generator_job(status);
CREATE INDEX IF NOT EXISTS idx_tnm_generator_job_job_id ON tnm_generator_job(job_id);
