-- Module 26: Workflow Intelligence (Finance OS)

CREATE SCHEMA IF NOT EXISTS finance_os;

CREATE TABLE IF NOT EXISTS finance_os.workflow_snapshots (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  workflow_instance_id uuid NOT NULL,
  workflow_definition_id uuid NULL,
  workflow_type varchar(100) NOT NULL,
  entity_type varchar(64) NULL,
  entity_id uuid NULL,
  started_at timestamptz NULL,
  completed_at timestamptz NULL,
  duration_seconds bigint NOT NULL DEFAULT 0,
  status varchar(30) NOT NULL DEFAULT 'running',
  efficiency_score numeric(5,2) NOT NULL DEFAULT 0,
  health_score numeric(5,2) NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE finance_os.workflow_snapshots ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='finance_os' AND tablename='workflow_snapshots'
      AND policyname='workflow_snapshots_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY workflow_snapshots_org_isolation ON finance_os.workflow_snapshots
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_fin_os_wf_snap_inst ON finance_os.workflow_snapshots(org_id, workflow_instance_id);
CREATE INDEX IF NOT EXISTS idx_fin_os_wf_snap_type ON finance_os.workflow_snapshots(org_id, workflow_type);

CREATE TABLE IF NOT EXISTS finance_os.workflow_stage_metrics (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  workflow_instance_id uuid NOT NULL,
  stage_name varchar(255) NOT NULL,
  step_key varchar(128) NULL,
  step_type varchar(64) NULL,
  assignee_id uuid NULL,
  entered_at timestamptz NULL,
  exited_at timestamptz NULL,
  duration_seconds bigint NOT NULL DEFAULT 0,
  queue_seconds bigint NOT NULL DEFAULT 0,
  approval_seconds bigint NOT NULL DEFAULT 0,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE finance_os.workflow_stage_metrics ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='finance_os' AND tablename='workflow_stage_metrics'
      AND policyname='workflow_stage_metrics_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY workflow_stage_metrics_org_isolation ON finance_os.workflow_stage_metrics
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_fin_os_wf_stage_inst ON finance_os.workflow_stage_metrics(org_id, workflow_instance_id);
CREATE INDEX IF NOT EXISTS idx_fin_os_wf_stage_key ON finance_os.workflow_stage_metrics(org_id, step_key);

CREATE TABLE IF NOT EXISTS finance_os.workflow_predictions (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  workflow_instance_id uuid NOT NULL,
  prediction_type varchar(100) NOT NULL,
  predicted_value text NOT NULL,
  confidence_score numeric(5,2) NOT NULL DEFAULT 0,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE finance_os.workflow_predictions ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='finance_os' AND tablename='workflow_predictions'
      AND policyname='workflow_predictions_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY workflow_predictions_org_isolation ON finance_os.workflow_predictions
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_fin_os_wf_pred_inst ON finance_os.workflow_predictions(org_id, workflow_instance_id);

CREATE TABLE IF NOT EXISTS finance_os.workflow_recommendations (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  workflow_type varchar(100) NOT NULL,
  workflow_instance_id uuid NULL,
  recommendation_type varchar(100) NOT NULL,
  recommendation text NOT NULL,
  impact_score numeric(5,2) NOT NULL DEFAULT 0,
  status varchar(30) NOT NULL DEFAULT 'open',
  accepted_by uuid NULL,
  accepted_at timestamptz NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE finance_os.workflow_recommendations ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='finance_os' AND tablename='workflow_recommendations'
      AND policyname='workflow_recommendations_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY workflow_recommendations_org_isolation ON finance_os.workflow_recommendations
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_fin_os_wf_rec_type ON finance_os.workflow_recommendations(org_id, workflow_type);
CREATE INDEX IF NOT EXISTS idx_fin_os_wf_rec_status ON finance_os.workflow_recommendations(org_id, status);

-- Extend M2 latency samples for stage-level observability
ALTER TABLE workflow.latency_samples ADD COLUMN IF NOT EXISTS step_key varchar(128) NULL;
ALTER TABLE workflow.latency_samples ADD COLUMN IF NOT EXISTS assignee_id uuid NULL;
