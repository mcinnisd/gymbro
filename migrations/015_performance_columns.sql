-- Migration 015: Add performance-specific columns for faster analytics
ALTER TABLE public.garmin_activities 
ADD COLUMN IF NOT EXISTS average_hr numeric,
ADD COLUMN IF NOT EXISTS max_hr numeric,
ADD COLUMN IF NOT EXISTS elevation_gain numeric,
ADD COLUMN IF NOT EXISTS average_speed numeric,
ADD COLUMN IF NOT EXISTS max_speed numeric,
ADD COLUMN IF NOT EXISTS average_cadence numeric;

ALTER TABLE public.strava_activities 
ADD COLUMN IF NOT EXISTS average_hr numeric,
ADD COLUMN IF NOT EXISTS max_hr numeric,
ADD COLUMN IF NOT EXISTS elevation_gain numeric,
ADD COLUMN IF NOT EXISTS average_speed numeric,
ADD COLUMN IF NOT EXISTS max_speed numeric,
ADD COLUMN IF NOT EXISTS average_cadence numeric;
