-- Module 27: Enterprise Financial Memory System (Finance OS)

CREATE SCHEMA IF NOT EXISTS finance_os;

CREATE TABLE IF NOT EXISTS finance_os.memory_entries (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  memory_type varchar(100) NOT NULL,
  entity_type varchar(100) NULL,
  entity_id uuid NULL,
  title text NOT NULL,
  content text NOT NULL,
  importance_score numeric(5,2) NOT NULL DEFAULT 0,
  importance_band varchar(32) NOT NULL DEFAULT 'medium',
  status varchar(32) NOT NULL DEFAULT 'active',
  ttl_policy varchar(32) NOT NULL DEFAULT '90d',
  source_event_type varchar(128) NULL,
  memory_record_id uuid NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NULL
);

ALTER TABLE finance_os.memory_entries ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='finance_os' AND tablename='memory_entries'
      AND policyname='memory_entries_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY memory_entries_org_isolation ON finance_os.memory_entries
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_fin_os_mem_type ON finance_os.memory_entries(org_id, memory_type);
CREATE INDEX IF NOT EXISTS idx_fin_os_mem_entity ON finance_os.memory_entries(org_id, entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_fin_os_mem_importance ON finance_os.memory_entries(org_id, importance_score DESC);
CREATE INDEX IF NOT EXISTS idx_fin_os_mem_status ON finance_os.memory_entries(org_id, status);

CREATE TABLE IF NOT EXISTS finance_os.memory_embeddings (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  memory_id uuid NOT NULL REFERENCES finance_os.memory_entries(id) ON DELETE CASCADE,
  embedding vector(1536),
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE finance_os.memory_embeddings ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='finance_os' AND tablename='memory_embeddings'
      AND policyname='memory_embeddings_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY memory_embeddings_org_isolation ON finance_os.memory_embeddings
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_fin_os_mem_emb_memory ON finance_os.memory_embeddings(org_id, memory_id);

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_am WHERE amname = 'hnsw') THEN
    EXECUTE 'CREATE INDEX IF NOT EXISTS idx_fin_os_mem_emb_hnsw ON finance_os.memory_embeddings USING hnsw (embedding vector_cosine_ops)';
  ELSE
    EXECUTE 'CREATE INDEX IF NOT EXISTS idx_fin_os_mem_emb_ivf ON finance_os.memory_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50)';
  END IF;
EXCEPTION WHEN OTHERS THEN
  NULL;
END $$;

CREATE TABLE IF NOT EXISTS finance_os.memory_references (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  memory_id uuid NOT NULL REFERENCES finance_os.memory_entries(id) ON DELETE CASCADE,
  source_type varchar(100) NOT NULL,
  source_id uuid NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE finance_os.memory_references ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='finance_os' AND tablename='memory_references'
      AND policyname='memory_references_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY memory_references_org_isolation ON finance_os.memory_references
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_fin_os_mem_ref_memory ON finance_os.memory_references(org_id, memory_id);
