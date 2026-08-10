-- Platform operator control plane: ops.* permissions + platform_owner role.
--
-- The permission keys ops.worker.manage and ops.queue.manage are required by
-- api/routes/ops.py, queue.py, ingestion.py and platform_events.py, but were
-- never inserted into the catalog, so require_permission() could never pass for
-- any principal. They are deliberately NOT granted to tenant_admin: that role
-- belongs to a customer-company admin, and the ops control plane is ours.

-- core.permissions is FORCE RLS with a SELECT-only policy (083), which blocks
-- INSERT even for the table owner. Relax for this transaction only; DDL is
-- transactional, so a failure here rolls the table back to FORCE.
ALTER TABLE core.permissions NO FORCE ROW LEVEL SECURITY;

INSERT INTO core.permissions (resource, action, description)
VALUES
    ('ops.worker', 'manage', 'Run queue workers, worker webhook consume'),
    ('ops.queue', 'manage', 'Enqueue/process jobs, DLQ requeue, event replay')
ON CONFLICT (resource, action) DO NOTHING;

ALTER TABLE core.permissions FORCE ROW LEVEL SECURITY;

-- core.roles / core.role_permissions are FORCE RLS and org-scoped.
SELECT set_config('app.current_org', '11111111-1111-4111-8111-111111111111', true);

INSERT INTO core.roles (id, org_id, name, description, system_role, policy_context)
VALUES (
    'b0000001-0001-4001-8001-0000000000f1'::uuid,
    '11111111-1111-4111-8111-111111111111'::uuid,
    'platform_owner',
    'Platform operator (SaaS owner): full product access plus ops control plane',
    TRUE,
    '{"max_approve_amount": null}'::jsonb
)
ON CONFLICT DO NOTHING;

-- Every catalog permission, including the two ops.* keys added above. Unlike the
-- 009 seed this is re-runnable: a later migration that adds permissions can
-- repeat this block to keep the role complete.
INSERT INTO core.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM core.roles r
CROSS JOIN core.permissions p
WHERE r.org_id = '11111111-1111-4111-8111-111111111111'::uuid
  AND r.name = 'platform_owner'
ON CONFLICT DO NOTHING;
