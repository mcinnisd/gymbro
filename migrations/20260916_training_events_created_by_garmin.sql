-- Allow wearable sync to mirror completed activities onto the calendar.
-- Live symptom: Garmin sync upserts created_by='garmin' and Postgres rejects
-- training_events_created_by_check (allowed only user|coach|agent).
-- Also keep event_type CHECK as-is; Garmin "running" is mapped to "run" in app code.

ALTER TABLE public.training_events
  DROP CONSTRAINT IF EXISTS training_events_created_by_check;

ALTER TABLE public.training_events
  ADD CONSTRAINT training_events_created_by_check
  CHECK (created_by IN ('user', 'coach', 'agent', 'garmin', 'strava'));
