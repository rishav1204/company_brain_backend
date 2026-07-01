-- Configurable segregation-of-duties conflict matrix.

CREATE TABLE IF NOT EXISTS governance.sod_conflicts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    role_a VARCHAR(128) NOT NULL,
    role_b VARCHAR(128) NOT NULL,
    scope VARCHAR(64) NOT NULL DEFAULT 'org',
    description TEXT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (org_id, role_a, role_b, scope)
);

CREATE INDEX IF NOT EXISTS governance_sod_conflicts_org_idx
    ON governance.sod_conflicts (org_id)
    WHERE active = TRUE;
