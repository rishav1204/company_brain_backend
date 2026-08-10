-- SEC-11/SEC-25/SEC-26: RLS on MFA tables + FORCE RLS on core.sessions

-- MFA and device tables (073) — enable RLS with tenant policies
ALTER TABLE core.user_mfa_methods ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.user_devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.trusted_devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.recovery_codes ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.org_security_policy ENABLE ROW LEVEL SECURITY;

ALTER TABLE core.user_mfa_methods FORCE ROW LEVEL SECURITY;
ALTER TABLE core.user_devices FORCE ROW LEVEL SECURITY;
ALTER TABLE core.trusted_devices FORCE ROW LEVEL SECURITY;
ALTER TABLE core.recovery_codes FORCE ROW LEVEL SECURITY;
ALTER TABLE core.org_security_policy FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS core_user_mfa_methods_tenant ON core.user_mfa_methods;
CREATE POLICY core_user_mfa_methods_tenant ON core.user_mfa_methods
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

DROP POLICY IF EXISTS core_user_devices_tenant ON core.user_devices;
CREATE POLICY core_user_devices_tenant ON core.user_devices
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

DROP POLICY IF EXISTS core_trusted_devices_tenant ON core.trusted_devices;
CREATE POLICY core_trusted_devices_tenant ON core.trusted_devices
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

DROP POLICY IF EXISTS core_recovery_codes_tenant ON core.recovery_codes;
CREATE POLICY core_recovery_codes_tenant ON core.recovery_codes
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

DROP POLICY IF EXISTS core_org_security_policy_tenant ON core.org_security_policy;
CREATE POLICY core_org_security_policy_tenant ON core.org_security_policy
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

-- Sessions — FORCE RLS (SEC-25)
ALTER TABLE core.sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.sessions FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS core_sessions_tenant ON core.sessions;
CREATE POLICY core_sessions_tenant ON core.sessions
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());
