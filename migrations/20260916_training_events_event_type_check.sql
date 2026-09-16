-- Live training_events_event_type_check originally allowed only
-- run|strength|rest|race|other. Remirror then failed on mapped Garmin values
-- such as cross_train. Live was widened to also allow
-- cross_train|ride|swim|walk|hike. Recreate that CHECK so git matches live.
--
-- Writers still map unknown Garmin typeKeys to 'other' rather than growing
-- this enum for every Garmin activity type.

ALTER TABLE public.training_events
  DROP CONSTRAINT IF EXISTS training_events_event_type_check;

ALTER TABLE public.training_events
  ADD CONSTRAINT training_events_event_type_check
  CHECK (event_type IN (
    'run', 'strength', 'rest', 'race', 'other',
    'cross_train', 'ride', 'swim', 'walk', 'hike'
  ));
