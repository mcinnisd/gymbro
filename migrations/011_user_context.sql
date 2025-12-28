-- Migration: 011_user_context.sql
-- Purpose: Create user_context table for storing interview answers, profile info, and training context
-- Uses pgvector for semantic search of relevant context

-- Enable pgvector extension (if not already enabled)
CREATE EXTENSION IF NOT EXISTS vector;

-- Create user_context table
CREATE TABLE IF NOT EXISTS user_context (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    context_type VARCHAR(50) NOT NULL,
    -- Types: 'profile', 'training', 'nutrition', 'injury', 'goal', 'plan', 'interview_answer'
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    -- Stores additional info like question_number, step, etc.
    embedding vector(1536),
    -- OpenAI's text-embedding-3-small produces 1536-dim vectors
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_user_context_user_id ON user_context(user_id);
CREATE INDEX IF NOT EXISTS idx_user_context_type ON user_context(context_type);

-- Create vector index for semantic search (IVF for better performance on large datasets)
CREATE INDEX IF NOT EXISTS idx_user_context_embedding ON user_context 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Update trigger for updated_at
CREATE OR REPLACE FUNCTION update_user_context_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_user_context_updated_at
    BEFORE UPDATE ON user_context
    FOR EACH ROW
    EXECUTE FUNCTION update_user_context_updated_at();

-- Add interview_step column to users table to track current interview progress
ALTER TABLE users ADD COLUMN IF NOT EXISTS interview_step INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS interview_started_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS interview_completed_at TIMESTAMP WITH TIME ZONE;
