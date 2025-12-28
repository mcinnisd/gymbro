-- Add embedding column to memories table
ALTER TABLE memories ADD COLUMN IF NOT EXISTS embedding vector(1536);

-- Create index for faster search (IVFFlat requires data, so we'll create it later or use HNSW if available)
-- For now, we'll skip index creation as table is empty, but here is the command for reference:
-- CREATE INDEX ON memories USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Function to match memories using cosine similarity
create or replace function match_memories (
  query_embedding vector(1536),
  match_threshold float,
  match_count int,
  p_user_id uuid
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
