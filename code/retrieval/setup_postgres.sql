-- Setup script for PostgreSQL with pgvector extension for NLWeb
-- This script creates the necessary database schema for vector similarity search

CREATE DATABASE nlweb_db;  -- Create the database if it doesn't exist

-- First, make sure pgvector extension is installed
CREATE EXTENSION IF NOT EXISTS vector;

DROP TABLE IF EXISTS documents CASCADE;  -- Drop existing table if it exists
-- Create the documents table

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,              -- Document ID (URL or other unique identifier)
    url TEXT NOT NULL,               -- URL of the document
    name TEXT NOT NULL,              -- Name of the document (title or similar)
    schema_json JSONB NOT NULL,      -- JSON schema of the document
    site TEXT NOT NULL,              -- Site or domain of the document
    embedding vector(1536) NOT NULL  -- Vector embedding (adjust dimension to match your model)
);

-- Create indexes for performance
-- Vector index for cosine similarity (adjust parameters based on your dataset size)
CREATE INDEX IF NOT EXISTS embedding_cosine_idx 
ON documents USING hnsw (embedding vector_cosine_ops) 
WITH (m = 16, ef_construction = 200);

-- -- Regular index on source for filtering
-- CREATE INDEX IF NOT EXISTS source_idx ON documents(source);

-- Example search queries:

-- Cosine similarity search (normalized inner product, preferred for OpenAI embeddings)
-- SELECT 
--     matched_text, 
--     embedding <=> '[0.1, 0.2, ..., 0.3]'::vector AS similarity_score,
--     source, 
--     context
-- FROM documents 
-- ORDER BY similarity_score
-- LIMIT 10;

-- Inner product search
-- SELECT 
--     matched_text, 
--     embedding <#> '[0.1, 0.2, ..., 0.3]'::vector AS similarity_score,
--     source, 
--     context
-- FROM documents 
-- ORDER BY similarity_score
-- LIMIT 10;

-- Euclidean distance search
-- SELECT 
--     matched_text, 
--     embedding <-> '[0.1, 0.2, ..., 0.3]'::vector AS similarity_score,
--     source, 
--     context
-- FROM documents 
-- ORDER BY similarity_score
-- LIMIT 10;

-- Filter by source with similarity search
-- SELECT 
--     matched_text, 
--     embedding <=> '[0.1, 0.2, ..., 0.3]'::vector AS similarity_score,
--     source, 
--     context
-- FROM documents 
-- WHERE source = 'docs'
-- ORDER BY similarity_score
-- LIMIT 10;
