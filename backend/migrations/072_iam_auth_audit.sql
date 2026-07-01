-- Auth audit log and session activity tracking.

ALTER TABLE core.sessions
    ADD COLUMN IF NOT EXISTS last_active_at TIMESTAMPTZ;

UPDATE core.sessions SET last_active_at = created_at WHERE last_active_at IS NULL;

CREATE TABLE IF NOT EXISTS core.auth_audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID REFERENCES core.organizations(id) ON DELETE SET NULL,
    user_id UUID,
    event VARCHAR(64) NOT NULL,
    success BOOLEAN NOT NULL DEFAULT TRUE,
    reason TEXT,
    ip_address INET,
    user_agent TEXT,
    session_id UUID,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS core_auth_audit_log_org_created_idx
    ON core.auth_audit_log (org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS core_auth_audit_log_user_created_idx
    ON core.auth_audit_log (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS core_auth_audit_log_event_idx
    ON core.auth_audit_log (event, created_at DESC);

CREATE TABLE IF NOT EXISTS core.password_reset_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS core_password_reset_tokens_user_idx
    ON core.password_reset_tokens (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS core.password_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS core_password_history_user_idx
    ON core.password_history (user_id, created_at DESC);
