-- Module 33: Finance Audit Explorer — materialized timelines (never replace audit_logs)

CREATE SCHEMA IF NOT EXISTS finance_audit;

CREATE TABLE IF NOT EXISTS finance_audit.audit_timelines (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL,
  object_type varchar(100) NOT NULL,
  object_id uuid NOT NULL,
  event_type varchar(100) NOT NULL,
  actor_id uuid,
  event_timestamp timestamptz NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  source_audit_log_id uuid,
  source_event_id uuid,
  trace_id uuid,
  object_ref text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_fin_audit_timelines_source_log
  ON finance_audit.audit_timelines (org_id, source_audit_log_id)
  WHERE source_audit_log_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_fin_audit_timelines_source_event
  ON finance_audit.audit_timelines (org_id, source_event_id, object_type, object_id, event_type)
  WHERE source_event_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_fin_audit_timelines_object_time
  ON finance_audit.audit_timelines (org_id, object_type, object_id, event_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_fin_audit_timelines_trace
  ON finance_audit.audit_timelines (org_id, trace_id)
  WHERE trace_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_fin_audit_timelines_metadata_gin
  ON finance_audit.audit_timelines USING gin (metadata);

ALTER TABLE finance_audit.audit_timelines ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='finance_audit' AND tablename='audit_timelines'
      AND policyname='audit_timelines_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY audit_timelines_org_isolation ON finance_audit.audit_timelines
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS finance_audit.audit_evidence (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL,
  timeline_id uuid NOT NULL REFERENCES finance_audit.audit_timelines(id),
  evidence_type varchar(100) NOT NULL,
  evidence_ref text NOT NULL,
  governance_evidence_id uuid,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_fin_audit_evidence_timeline
  ON finance_audit.audit_evidence (org_id, timeline_id);

ALTER TABLE finance_audit.audit_evidence ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='finance_audit' AND tablename='audit_evidence'
      AND policyname='audit_evidence_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY audit_evidence_org_isolation ON finance_audit.audit_evidence
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS finance_audit.ai_decision_trails (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL,
  agent_execution_id uuid,
  ai_trace_id uuid,
  recommendation_id uuid,
  decision_type varchar(100) NOT NULL,
  input_context jsonb NOT NULL DEFAULT '{}'::jsonb,
  reasoning_summary text NOT NULL,
  confidence_score numeric(5,2),
  outcome varchar(64),
  approved_by uuid,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_fin_audit_ai_traces_trace
  ON finance_audit.ai_decision_trails (org_id, ai_trace_id)
  WHERE ai_trace_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_fin_audit_ai_traces_rec
  ON finance_audit.ai_decision_trails (org_id, recommendation_id)
  WHERE recommendation_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_fin_audit_ai_trails_execution
  ON finance_audit.ai_decision_trails (org_id, agent_execution_id, created_at DESC)
  WHERE agent_execution_id IS NOT NULL;

ALTER TABLE finance_audit.ai_decision_trails ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='finance_audit' AND tablename='ai_decision_trails'
      AND policyname='ai_decision_trails_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY ai_decision_trails_org_isolation ON finance_audit.ai_decision_trails
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

-- Append-only enforcement
CREATE OR REPLACE FUNCTION finance_audit.prevent_timeline_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'finance_audit.audit_timelines is append-only';
END;
$$;

DROP TRIGGER IF EXISTS audit_timelines_no_update ON finance_audit.audit_timelines;
CREATE TRIGGER audit_timelines_no_update
BEFORE UPDATE OR DELETE ON finance_audit.audit_timelines
FOR EACH ROW EXECUTE FUNCTION finance_audit.prevent_timeline_mutation();

CREATE OR REPLACE FUNCTION finance_audit.prevent_evidence_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'finance_audit.audit_evidence is append-only';
END;
$$;

DROP TRIGGER IF EXISTS audit_evidence_no_update ON finance_audit.audit_evidence;
CREATE TRIGGER audit_evidence_no_update
BEFORE UPDATE OR DELETE ON finance_audit.audit_evidence
FOR EACH ROW EXECUTE FUNCTION finance_audit.prevent_evidence_mutation();

CREATE OR REPLACE FUNCTION finance_audit.prevent_ai_trail_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'finance_audit.ai_decision_trails is append-only';
END;
$$;

DROP TRIGGER IF EXISTS ai_decision_trails_no_update ON finance_audit.ai_decision_trails;
CREATE TRIGGER ai_decision_trails_no_update
BEFORE UPDATE OR DELETE ON finance_audit.ai_decision_trails
FOR EACH ROW EXECUTE FUNCTION finance_audit.prevent_ai_trail_mutation();

-- Retention seed extension
INSERT INTO governance.retention_policies (org_id, resource_type, retain_years, archive_after_days)
SELECT o.id, r.resource_type, 8, 365
FROM core.organizations o
CROSS JOIN (
  VALUES ('audit_timelines'), ('ai_decision_trails')
) AS r(resource_type)
ON CONFLICT (org_id, resource_type) DO NOTHING;
