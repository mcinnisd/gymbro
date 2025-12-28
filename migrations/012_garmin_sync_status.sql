-- Migration: 012_garmin_sync_status.sql
-- Purpose: Add sync status tracking for Garmin integration

ALTER TABLE users ADD COLUMN IF NOT EXISTS garmin_sync_status VARCHAR(50) DEFAULT 'not_connected';
-- Possible values: 'not_connected', 'connected', 'syncing', 'synced', 'error'

ALTER TABLE users ADD COLUMN IF NOT EXISTS garmin_last_sync_error TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS garmin_sync_started_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS garmin_sync_completed_at TIMESTAMP WITH TIME ZONE;
