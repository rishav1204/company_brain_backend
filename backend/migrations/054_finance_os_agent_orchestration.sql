-- Module 29: AI Agent Orchestration Layer (Finance OS)

CREATE SCHEMA IF NOT EXISTS finance_os;

CREATE TABLE IF NOT EXISTS finance_os.agent_executions (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  platform_run_id uuid NULL,
  agent_name varchar(100) NOT NULL,
  task_type varchar(100) NULL,
  trigger_type varchar(64) NOT NULL DEFAULT 'api',
  status varchar(50) NOT NULL DEFAULT 'running',
  source_event_type varchar(128) NULL,
  entity_type varchar(100) NULL,
  entity_id varchar(100) NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  started_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE finance_os.agent_executions ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='finance_os' AND tablename='agent_executions'
      AND policyname='agent_executions_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY agent_executions_org_isolation ON finance_os.agent_executions
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_fin_os_agent_exec_org ON finance_os.agent_executions(org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_fin_os_agent_exec_agent ON finance_os.agent_executions(org_id, agent_name);
CREATE INDEX IF NOT EXISTS idx_fin_os_agent_exec_status ON finance_os.agent_executions(org_id, status);
CREATE INDEX IF NOT EXISTS idx_fin_os_agent_exec_entity ON finance_os.agent_executions(org_id, entity_type, entity_id);

CREATE TABLE IF NOT EXISTS finance_os.agent_recommendations (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  execution_id uuid NOT NULL REFERENCES finance_os.agent_executions(id) ON DELETE CASCADE,
  recommendation_type varchar(100) NOT NULL,
  recommendation text NOT NULL,
  confidence_score numeric(5,2) NOT NULL DEFAULT 0,
  confidence_band varchar(32) NOT NULL DEFAULT 'manual',
  approval_required boolean NOT NULL DEFAULT true,
  workflow_instance_id uuid NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  status varchar(32) NOT NULL DEFAULT 'proposed',
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE finance_os.agent_recommendations ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='finance_os' AND tablename='agent_recommendations'
      AND policyname='agent_recommendations_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY agent_recommendations_org_isolation ON finance_os.agent_recommendations
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_fin_os_agent_rec_exec ON finance_os.agent_recommendations(org_id, execution_id);
CREATE INDEX IF NOT EXISTS idx_fin_os_agent_rec_status ON finance_os.agent_recommendations(org_id, status);
