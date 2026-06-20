-- Module 28: Operational Graph Engine — audit metadata only (Neo4j stores graph structure)

CREATE SCHEMA IF NOT EXISTS finance_os;

CREATE TABLE IF NOT EXISTS finance_os.graph_sync_events (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  source_event_type varchar(128) NULL,
  entity_type varchar(100) NULL,
  entity_id varchar(100) NULL,
  mutation_type varchar(64) NOT NULL DEFAULT 'node_upsert',
  status varchar(32) NOT NULL DEFAULT 'success',
  trace_id varchar(128) NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE finance_os.graph_sync_events ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='finance_os' AND tablename='graph_sync_events'
      AND policyname='graph_sync_events_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY graph_sync_events_org_isolation ON finance_os.graph_sync_events
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_fin_os_graph_sync_org ON finance_os.graph_sync_events(org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_fin_os_graph_sync_entity ON finance_os.graph_sync_events(org_id, entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_fin_os_graph_sync_status ON finance_os.graph_sync_events(org_id, status);
