-- DB-01 completion: ENABLE + FORCE RLS on remaining core/erp tables

ALTER TABLE core.departments ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.departments FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS core_departments_org ON core.departments;
CREATE POLICY core_departments_org ON core.departments
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

ALTER TABLE core.auth_audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.auth_audit_log FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS core_auth_audit_org ON core.auth_audit_log;
CREATE POLICY core_auth_audit_org ON core.auth_audit_log
    USING (org_id IS NULL OR org_id = app_current_org_id())
    WITH CHECK (org_id IS NULL OR org_id = app_current_org_id());

ALTER TABLE core.password_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.password_history FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS core_password_history_org ON core.password_history;
CREATE POLICY core_password_history_org ON core.password_history
    USING (
        EXISTS (
            SELECT 1 FROM core.users u
            WHERE u.id = core.password_history.user_id
              AND u.org_id = app_current_org_id()
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM core.users u
            WHERE u.id = core.password_history.user_id
              AND u.org_id = app_current_org_id()
        )
    );

ALTER TABLE core.password_reset_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.password_reset_tokens FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS core_password_reset_tokens_org ON core.password_reset_tokens;
CREATE POLICY core_password_reset_tokens_org ON core.password_reset_tokens
    USING (
        EXISTS (
            SELECT 1 FROM core.users u
            WHERE u.id = core.password_reset_tokens.user_id
              AND u.org_id = app_current_org_id()
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM core.users u
            WHERE u.id = core.password_reset_tokens.user_id
              AND u.org_id = app_current_org_id()
        )
    );

ALTER TABLE core.permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.permissions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS core_permissions_read ON core.permissions;
CREATE POLICY core_permissions_read ON core.permissions
    FOR SELECT USING (true);

ALTER TABLE core.role_permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.role_permissions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS core_role_permissions_org ON core.role_permissions;
CREATE POLICY core_role_permissions_org ON core.role_permissions
    USING (
        EXISTS (
            SELECT 1 FROM core.roles r
            WHERE r.id = core.role_permissions.role_id
              AND r.org_id = app_current_org_id()
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM core.roles r
            WHERE r.id = core.role_permissions.role_id
              AND r.org_id = app_current_org_id()
        )
    );

ALTER TABLE erp.compliance_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE erp.compliance_types FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS erp_compliance_types_read ON erp.compliance_types;
CREATE POLICY erp_compliance_types_read ON erp.compliance_types
    FOR SELECT USING (true);

-- Ensure FORCE RLS on every core/erp table that has RLS enabled
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT n.nspname AS schema_name, c.relname AS table_name
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname IN ('core', 'erp')
          AND c.relkind = 'r'
          AND c.relrowsecurity = true
    LOOP
        EXECUTE format('ALTER TABLE %I.%I FORCE ROW LEVEL SECURITY', r.schema_name, r.table_name);
    END LOOP;
END $$;
