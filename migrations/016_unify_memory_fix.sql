-- Fix migration for unified memory
-- Handles idempotency and missing 'memories' table

DO $$
BEGIN
    -- 1. Migrate user_context_deprecated if user_intelligence is empty
    -- Check if user_intelligence is empty
    IF (SELECT count(*) FROM user_intelligence) = 0 THEN
        -- Check if source table exists
        IF EXISTS (SELECT FROM pg_tables WHERE tablename = 'user_context_deprecated') THEN
            INSERT INTO user_intelligence (user_id, content, category, metadata, created_at)
            SELECT 
                user_id, 
                content, 
                context_type as category, 
                metadata, 
                created_at
            FROM user_context_deprecated;
        ELSIF EXISTS (SELECT FROM pg_tables WHERE tablename = 'user_context') THEN
             INSERT INTO user_intelligence (user_id, content, category, metadata, created_at)
            SELECT 
                user_id, 
                content, 
                context_type as category, 
                metadata, 
                created_at
            FROM user_context;
        END IF;
    END IF;

    -- 2. Rename tables if not already renamed
    IF EXISTS (SELECT FROM pg_tables WHERE tablename = 'user_context') THEN
        ALTER TABLE user_context RENAME TO user_context_deprecated;
    END IF;
    
    -- 3. Memories (skip if not exists)
    IF EXISTS (SELECT FROM pg_tables WHERE tablename = 'memories') THEN
        INSERT INTO user_intelligence (user_id, content, category, created_at)
        SELECT 
            user_id, 
            content, 
            COALESCE(memory_type, 'fact') as category, 
            created_at
        FROM memories;
        
        ALTER TABLE memories RENAME TO memories_deprecated;
    END IF;
    
END $$;
