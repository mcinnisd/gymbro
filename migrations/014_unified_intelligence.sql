-- Migration: 014_unified_intelligence.sql
-- Purpose: Unify memories and user_context into a single intelligent storage layer
-- Uses 768-dimensional vectors for Google Gemini embeddings

-- Create unified intelligence table
CREATE TABLE IF NOT EXISTS user_intelligence (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category VARCHAR(50) NOT NULL, 
    -- 'fact', 'preference', 'goal', 'injury', 'nutrition', 'training_philosophy', 'interaction'
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    embedding vector(768), -- Gemini standard dimension
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for basic filtering
CREATE INDEX IF NOT EXISTS idx_intelligence_user_id ON user_intelligence(user_id);
CREATE INDEX IF NOT EXISTS idx_intelligence_category ON user_intelligence(category);

-- HNSW Index for ultra-fast semantic search
-- HNSW is generally faster and more accurate than IVFFlat for high-dimensional vectors
CREATE INDEX IF NOT EXISTS idx_intelligence_embedding_hnsw ON user_intelligence 
USING hnsw (embedding vector_cosine_ops);

-- Search function for the new intelligence layer
CREATE OR REPLACE FUNCTION match_intelligence (
    query_embedding vector(768),
    match_user_id int,
    match_count int DEFAULT 5,
    match_threshold float DEFAULT 0.5,
    filter_categories varchar[] DEFAULT NULL
)
RETURNS TABLE (
    id int,
    content text,
    category varchar,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        ui.id,
        ui.content,
        ui.category,
        1 - (ui.embedding <=> query_embedding) AS similarity
    FROM user_intelligence ui
    WHERE ui.user_id = match_user_id
    AND (filter_categories IS NULL OR ui.category = ANY(filter_categories))
    AND 1 - (ui.embedding <=> query_embedding) > match_threshold
    ORDER BY ui.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_intelligence_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_intelligence_updated_at
    BEFORE UPDATE ON user_intelligence
    FOR EACH ROW
    EXECUTE FUNCTION update_intelligence_updated_at();
