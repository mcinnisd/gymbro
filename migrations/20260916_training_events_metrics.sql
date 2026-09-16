-- Live training_events was created before canonical schema.sql added metrics.
-- Remirror 77dc61f wrote metrics jsonb and Postgres returned 42703
-- (column training_events.metrics does not exist).
-- Safe to apply alongside created_by=garmin CHECK; IF NOT EXISTS is idempotent.

ALTER TABLE public.training_events
  ADD COLUMN IF NOT EXISTS metrics JSONB DEFAULT '{}'::jsonb;
