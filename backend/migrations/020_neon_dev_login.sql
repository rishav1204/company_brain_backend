-- Dev login: tenant_admin should not require MFA enrollment for local/Neon dev (prod can re-enable via role policy).
UPDATE core.roles
SET policy_context = policy_context - 'mfa_required'
WHERE org_id = '11111111-1111-4111-8111-111111111111'::uuid
  AND name = 'tenant_admin'
  AND (policy_context->>'mfa_required')::boolean IS TRUE;
