-- Chunked semantic embeddings for document search (page/section level)

CREATE SCHEMA IF NOT EXISTS documents;

CREATE TABLE IF NOT EXISTS documents.semantic_chunks (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  document_id uuid NOT NULL REFERENCES documents.documents(id) ON DELETE CASCADE,
  page_number int NULL,
  chunk_index int NOT NULL DEFAULT 0,
  content text NOT NULL,
  embedding vector(1536),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE documents.semantic_chunks ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_policies
    WHERE schemaname = 'documents' AND tablename = 'semantic_chunks' AND policyname = 'semantic_chunks_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY semantic_chunks_org_isolation
      ON documents.semantic_chunks
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_semantic_chunks_org_doc ON documents.semantic_chunks(org_id, document_id);
CREATE INDEX IF NOT EXISTS idx_semantic_chunks_keyword_gin ON documents.semantic_chunks USING GIN (to_tsvector('simple', content));

-- Optional HNSW index if available (pgvector >= 0.5).
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_am WHERE amname = 'hnsw') THEN
    EXECUTE 'CREATE INDEX IF NOT EXISTS idx_semantic_chunks_embedding_hnsw ON documents.semantic_chunks USING hnsw (embedding vector_cosine_ops)';
  END IF;
END
$$;

