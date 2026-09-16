-- garmin_activities.activity_id was UNIQUE globally. Upsert on_conflict=activity_id
-- reassigned the same Garmin workouts (Santa Monica runs) from user 2 onto user 100.
-- Scope uniqueness to (user_id, activity_id) so each athlete keeps their own rows.

ALTER TABLE public.garmin_activities
  DROP CONSTRAINT IF EXISTS garmin_activities_activity_id_key;

DROP INDEX IF EXISTS garmin_activities_activity_id_key;

CREATE UNIQUE INDEX IF NOT EXISTS garmin_activities_user_activity_id_key
  ON public.garmin_activities(user_id, activity_id);
