-- Department-scoped role assignments for ABAC.

CREATE TABLE IF NOT EXISTS core.departments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    department_code VARCHAR(64) NOT NULL,
    department_name VARCHAR(255) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (org_id, department_code)
);

CREATE INDEX IF NOT EXISTS core_departments_org_idx ON core.departments (org_id);

ALTER TABLE core.user_roles
    ADD COLUMN IF NOT EXISTS department_id UUID REFERENCES core.departments(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS core_user_roles_department_idx
    ON core.user_roles (department_id)
    WHERE department_id IS NOT NULL;
