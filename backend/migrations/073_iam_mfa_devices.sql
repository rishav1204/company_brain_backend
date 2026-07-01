-- MFA methods, devices, trusted devices, recovery codes, org security policy.

CREATE TABLE IF NOT EXISTS core.user_mfa_methods (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    method VARCHAR(32) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, method)
);

CREATE INDEX IF NOT EXISTS core_user_mfa_methods_org_user_idx
    ON core.user_mfa_methods (org_id, user_id);

CREATE TABLE IF NOT EXISTS core.user_devices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    fingerprint TEXT NOT NULL,
    device_name TEXT,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, fingerprint)
);

CREATE INDEX IF NOT EXISTS core_user_devices_org_user_idx
    ON core.user_devices (org_id, user_id);

CREATE TABLE IF NOT EXISTS core.trusted_devices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    device_id UUID NOT NULL REFERENCES core.user_devices(id) ON DELETE CASCADE,
    trust_expires_at TIMESTAMPTZ NOT NULL,
    mfa_skip_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, device_id)
);

CREATE INDEX IF NOT EXISTS core_trusted_devices_org_user_idx
    ON core.trusted_devices (org_id, user_id);

CREATE TABLE IF NOT EXISTS core.recovery_codes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    code_hash TEXT NOT NULL,
    batch_id UUID NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS core_recovery_codes_user_batch_idx
    ON core.recovery_codes (user_id, batch_id);

CREATE TABLE IF NOT EXISTS core.org_security_policy (
    org_id UUID PRIMARY KEY REFERENCES core.organizations(id) ON DELETE CASCADE,
    required_methods JSONB NOT NULL DEFAULT '[]'::jsonb,
    grace_period_days INT NOT NULL DEFAULT 0,
    webauthn_required_for_admins BOOLEAN NOT NULL DEFAULT FALSE,
    max_concurrent_sessions INT NOT NULL DEFAULT 10,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Migrate existing TOTP secrets from core.users into user_mfa_methods.
INSERT INTO core.user_mfa_methods (org_id, user_id, method, enabled, metadata)
SELECT u.org_id, u.id, 'totp', u.mfa_enabled, jsonb_build_object('secret', u.mfa_secret)
FROM core.users u
WHERE u.mfa_secret IS NOT NULL AND trim(u.mfa_secret) <> ''
ON CONFLICT (user_id, method) DO NOTHING;
