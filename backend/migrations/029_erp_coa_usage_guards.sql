-- Module 8: Deactivation enforcement hooks (usage/balance guards)

CREATE SCHEMA IF NOT EXISTS erp;

CREATE TABLE IF NOT EXISTS erp.account_usage (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  account_id uuid NOT NULL REFERENCES erp.chart_of_accounts(id) ON DELETE CASCADE,
  has_balance boolean NOT NULL DEFAULT false,
  used_in_journals boolean NOT NULL DEFAULT false,
  last_seen_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.account_usage ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='erp' AND tablename='account_usage' AND policyname='account_usage_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY account_usage_org_isolation
      ON erp.account_usage
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_account_usage_org_account ON erp.account_usage(org_id, account_id);

