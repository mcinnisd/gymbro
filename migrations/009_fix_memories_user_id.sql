-- Fix user_id type in memories table to match public.users(id)

-- 1. Drop RLS policies that depend on user_id
DROP POLICY IF EXISTS "Users can read own memories" ON memories;
DROP POLICY IF EXISTS "Users can insert own memories" ON memories;
DROP POLICY IF EXISTS "Users can update own memories" ON memories;
DROP POLICY IF EXISTS "Users can delete own memories" ON memories;

-- 2. Disable RLS (since we are using custom auth and backend service role)
ALTER TABLE memories DISABLE ROW LEVEL SECURITY;

-- 3. Drop the foreign key to auth.users
ALTER TABLE memories DROP CONSTRAINT IF EXISTS memories_user_id_fkey;

-- 4. Alter the column type to BIGINT
ALTER TABLE memories ALTER COLUMN user_id TYPE BIGINT USING (CASE WHEN user_id::text ~ '^[0-9]+$' THEN user_id::text::bigint ELSE NULL END);

-- 5. Add foreign key to public.users
ALTER TABLE memories ADD CONSTRAINT memories_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

-- 6. Update the match_memories function to accept BIGINT user_id
DROP FUNCTION IF EXISTS match_memories;

create or replace function match_memories (
  query_embedding vector(1536),
  match_threshold float,
  match_count int,
  p_user_id bigint
)
returns table (
  id bigint,
  content text,
  memory_type text,
  similarity float
)
language plpgsql
as $$
begin
  return query
  select
    memories.id,
    memories.content,
    memories.memory_type,
    1 - (memories.embedding <=> query_embedding) as similarity
  from memories
  where 1 - (memories.embedding <=> query_embedding) > match_threshold
  and memories.user_id = p_user_id
  order by memories.embedding <=> query_embedding
  limit match_count;
end;
$$;
