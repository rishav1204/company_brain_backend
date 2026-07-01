-- Module 38: Platform AI Runtime (Cursor-style goal planner + execution graph)

CREATE SCHEMA IF NOT EXISTS finance_os;

CREATE TABLE IF NOT EXISTS finance_os.goals (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  goal_type varchar(32) NOT NULL DEFAULT 'user',
  title text NOT NULL,
  description text NULL,
  status varchar(32) NOT NULL DEFAULT 'draft',
  trigger_type varchar(64) NOT NULL DEFAULT 'chat',
  trigger_config jsonb NOT NULL DEFAULT '{}'::jsonb,
  world_state jsonb NOT NULL DEFAULT '{}'::jsonb,
  plan_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by varchar(255) NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz NULL
);

ALTER TABLE finance_os.goals ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='finance_os' AND tablename='goals'
      AND policyname='goals_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY goals_org_isolation ON finance_os.goals
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_fin_os_goals_org ON finance_os.goals(org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_fin_os_goals_status ON finance_os.goals(org_id, status);

CREATE TABLE IF NOT EXISTS finance_os.goal_runs (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  goal_id uuid NOT NULL REFERENCES finance_os.goals(id) ON DELETE CASCADE,
  status varchar(32) NOT NULL DEFAULT 'running',
  current_node_id varchar(64) NULL,
  human_approved boolean NOT NULL DEFAULT false,
  confidence_score numeric(5,2) NULL,
  risk_level varchar(32) NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  started_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz NULL
);

ALTER TABLE finance_os.goal_runs ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='finance_os' AND tablename='goal_runs'
      AND policyname='goal_runs_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY goal_runs_org_isolation ON finance_os.goal_runs
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_fin_os_goal_runs_goal ON finance_os.goal_runs(org_id, goal_id);

CREATE TABLE IF NOT EXISTS finance_os.execution_graphs (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  goal_run_id uuid NOT NULL REFERENCES finance_os.goal_runs(id) ON DELETE CASCADE,
  graph_version int NOT NULL DEFAULT 1,
  nodes jsonb NOT NULL DEFAULT '[]'::jsonb,
  edges jsonb NOT NULL DEFAULT '[]'::jsonb,
  reasoning text NULL,
  rollback_strategy jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE finance_os.execution_graphs ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='finance_os' AND tablename='execution_graphs'
      AND policyname='execution_graphs_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY execution_graphs_org_isolation ON finance_os.execution_graphs
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS finance_os.runtime_observations (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  goal_run_id uuid NOT NULL REFERENCES finance_os.goal_runs(id) ON DELETE CASCADE,
  node_id varchar(64) NOT NULL,
  tool_name varchar(128) NOT NULL,
  tool_method varchar(128) NOT NULL,
  status varchar(32) NOT NULL,
  result jsonb NOT NULL DEFAULT '{}'::jsonb,
  alternatives jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE finance_os.runtime_observations ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='finance_os' AND tablename='runtime_observations'
      AND policyname='runtime_observations_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY runtime_observations_org_isolation ON finance_os.runtime_observations
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_fin_os_obs_run ON finance_os.runtime_observations(org_id, goal_run_id, created_at DESC);
