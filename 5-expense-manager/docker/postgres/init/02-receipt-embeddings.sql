-- pgvector: semantic search over receipt text (RAG). Dimension 768 = Google text-embedding-004.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS receipt_embeddings (
    receipt_id INTEGER PRIMARY KEY REFERENCES receipts (id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding vector(768) NOT NULL
);

CREATE INDEX IF NOT EXISTS receipt_embeddings_embedding_hnsw
    ON receipt_embeddings
    USING hnsw (embedding vector_cosine_ops);
