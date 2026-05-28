INSERT INTO organizations (id, name, plan, created_at)
VALUES ('11111111-1111-4111-8111-111111111111'::uuid, 'Benchmark Org', 'enterprise', NOW())
ON CONFLICT (id) DO NOTHING;
