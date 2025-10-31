-- Add pgvector extension and embedding column for semantic search
-- Run this file: psql -h <host> -U <user> -d <database> -f scripts/add_vector_support.sql

-- Enable the pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding column to documents table (1536 dimensions for OpenAI text-embedding-3-small)
ALTER TABLE documents 
ADD COLUMN IF NOT EXISTS embedding vector(1536);

-- Create index for fast vector similarity search
CREATE INDEX IF NOT EXISTS documents_embedding_idx 
ON documents USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Add metadata columns for embedding tracking
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS embedding_model VARCHAR(100),
ADD COLUMN IF NOT EXISTS embedding_generated_at TIMESTAMP;

COMMENT ON COLUMN documents.embedding IS 'Vector embedding for semantic search (1536-dim from OpenAI text-embedding-3-small)';
COMMENT ON COLUMN documents.embedding_model IS 'Model used to generate embedding';
COMMENT ON COLUMN documents.embedding_generated_at IS 'Timestamp when embedding was generated';

