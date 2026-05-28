-- Module 6: Semantic search indexes for documents (pgvector)

-- Vector index for nearest-neighbor search.
-- NOTE: ivfflat requires ANALYZE and works best with enough rows; good default for early scale.
CREATE INDEX IF NOT EXISTS documents_semantic_embeddings_embedding_idx
    ON documents.semantic_embeddings
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Helpful metadata index for filters.
CREATE INDEX IF NOT EXISTS documents_semantic_embeddings_metadata_gin_idx
    ON documents.semantic_embeddings
    USING GIN (metadata);
