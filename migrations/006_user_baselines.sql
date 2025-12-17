-- User Baselines Cache Table
-- Pre-computed fitness baselines for fast context injection
-- Updated on login and periodically

CREATE TABLE IF NOT EXISTS user_baselines (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    metric_category VARCHAR(50) NOT NULL,  -- 'running', 'health', 'training_load'
    baselines JSONB NOT NULL,              -- Computed baseline values
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, metric_category)
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_user_baselines_user_id ON user_baselines(user_id);

-- Example baseline JSON structure for 'running':
-- {
--   "period_days": 90,
--   "activity_count": 25,
--   "avg_distance_m": 7500,
--   "avg_duration_sec": 2850,
--   "avg_pace_sec_km": 380,
--   "avg_hr": 152,
--   "avg_efficiency": 22.5,
--   "total_distance_km": 187.5,
--   "runs_per_week": 1.9
-- }

-- Example baseline JSON structure for 'health':
-- {
--   "avg_hrv": 55.2,
--   "avg_rhr": 48,
--   "avg_sleep_hours": 7.2
-- }

-- Example baseline JSON structure for 'training_load':
-- {
--   "last_7_days": {"distance_km": 45.2, "duration_hours": 5.1, "activity_count": 4},
--   "previous_7_days": {"distance_km": 38.1, "duration_hours": 4.3, "activity_count": 3},
--   "change": {"distance_pct": 18.6, "duration_pct": 18.6}
-- }
