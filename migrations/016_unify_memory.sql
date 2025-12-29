-- Migration: 016_unify_memory.sql
-- Purpose: Consolidate memories and user_context into user_intelligence
--          and deprecate the old tables.

-- 1. Migrate from 'memories'
INSERT INTO user_intelligence (user_id, content, category, created_at)
SELECT 
    user_id, 
    content, 
    COALESCE(memory_type, 'fact') as category, 
    created_at
FROM memories;

-- 2. Migrate from 'user_context'
-- Note: We discard the 1536-dim embeddings as they are incompatible with 768-dim
INSERT INTO user_intelligence (user_id, content, category, metadata, created_at)
SELECT 
    user_id, 
    content, 
    context_type as category, 
    metadata, 
    created_at
FROM user_context;

-- 3. Rename old tables to deprecated
ALTER TABLE memories RENAME TO memories_deprecated;
ALTER TABLE user_context RENAME TO user_context_deprecated;
