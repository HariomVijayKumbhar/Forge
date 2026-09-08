-- Forge Autonomous Agent: Supabase Postgres Schema
-- Paste this script directly into your Supabase project's SQL Editor (https://supabase.com/dashboard/project/_/sql)

-- 1. Runs Table
CREATE TABLE IF NOT EXISTS runs (
    id VARCHAR(64) PRIMARY KEY,
    repo_url TEXT NOT NULL,
    task TEXT NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'idle',
    provider_used VARCHAR(32),
    files_changed TEXT DEFAULT '[]',
    diff TEXT,
    tests_passed BOOLEAN,
    confidence INTEGER,
    summary TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs (status);

-- 2. Steps Table
CREATE TABLE IF NOT EXISTS steps (
    id BIGSERIAL PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    step_index INTEGER NOT NULL,
    action_type VARCHAR(32) NOT NULL,
    tool_name VARCHAR(64),
    tool_input TEXT,
    tool_output TEXT,
    status VARCHAR(32) NOT NULL DEFAULT 'ok',
    provider_used VARCHAR(32),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_steps_run_id ON steps (run_id, id ASC);

-- 3. Security Audit Log Table
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(64) NOT NULL,
    actor_ip VARCHAR(64),
    run_id VARCHAR(64),
    details TEXT,
    status VARCHAR(32) NOT NULL DEFAULT 'success',
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_run_id ON audit_log (run_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log (timestamp DESC);

-- 4. Revoked Tokens Table (Token Rotation & Blacklist)
CREATE TABLE IF NOT EXISTS revoked_tokens (
    jti VARCHAR(128) PRIMARY KEY,
    revoked_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_revoked_tokens_jti ON revoked_tokens (jti);

-- 5. Users Table (for registration and login)
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(64) PRIMARY KEY,
    username VARCHAR(64) NOT NULL UNIQUE,
    email VARCHAR(255),
    hashed_password TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);
