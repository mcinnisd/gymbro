-- Field-level provenance for biometrics_daily.
-- source stays the highest-priority contributor for the day.
-- field_sources records which source supplied each metric so a later null
-- upsert (Garmin remirror or sync) cannot wipe a filled Apple Health value,
-- and a lower-priority source cannot replace Garmin sleep or HRV.
-- Fitbit is a reserved slot in the priority order; this migration does not
-- add a Fitbit client.
--
-- Priority: garmin > strava > apple_health|healthkit > fitbit > manual.

ALTER TABLE public.biometrics_daily
  ADD COLUMN IF NOT EXISTS field_sources JSONB;

COMMENT ON COLUMN public.biometrics_daily.source IS
  'Highest-priority source that contributed a real value for this day. Priority: garmin > strava > apple_health|healthkit > fitbit (reserved, no API) > manual. Metrics merge field-by-field; see field_sources.';

COMMENT ON COLUMN public.biometrics_daily.field_sources IS
  'Map of metric field to the source that supplied the stored value. Null writes do not clear a filled value.';
