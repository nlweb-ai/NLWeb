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
CREATE INDEX IF NOT EXISTS embedding_cosine_idx_vector 
ON documents USING hnsw (embedding vector_cosine_ops) 
WITH (m = 16, ef_construction = 200);
