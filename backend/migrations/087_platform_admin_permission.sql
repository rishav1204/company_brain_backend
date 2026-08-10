-- Cross-tenant platform control plane: platform.admin permission.
--
-- Every other permission in this system is answered inside one org, because the
-- JWT carries a single org_id. platform.admin is the exception: it authorises
-- reading and mutating IAM state in ANY org, so it is granted only to the
-- platform_owner role from 086 and must never be attached to a customer role.

ALTER TABLE core.permissions NO FORCE ROW LEVEL SECURITY;

INSERT INTO core.permissions (resource, action, description)
VALUES ('platform', 'admin', 'Cross-tenant operator: read any org, suspend users, revoke sessions')
ON CONFLICT (resource, action) DO NOTHING;

ALTER TABLE core.permissions FORCE ROW LEVEL SECURITY;

SELECT set_config('app.current_org', '11111111-1111-4111-8111-111111111111', true);

INSERT INTO core.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM core.roles r
CROSS JOIN core.permissions p
WHERE r.org_id = '11111111-1111-4111-8111-111111111111'::uuid
  AND r.name = 'platform_owner'
  AND p.permission_key = 'platform.admin'
ON CONFLICT DO NOTHING;
