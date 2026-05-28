INSERT INTO organizations (id, name, plan, created_at)
VALUES ('22222222-2222-4222-8222-222222222222'::uuid, 'Tenant B Org', 'enterprise', NOW())
ON CONFLICT (id) DO NOTHING;
