-- Migration for Unified Health Intelligence Schema
CREATE TABLE IF NOT EXISTS biometrics_daily (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INT NOT NULL,
    date DATE NOT NULL,
    resting_hr INT,
    hrv_ms INT,
    sleep_hours NUMERIC(4,2),
    sleep_score INT,
    recovery_score INT,
    steps INT,
    calories_burned INT,
    raw_source VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS lab_panels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INT NOT NULL,
    test_date DATE NOT NULL,
    provider_name VARCHAR(100),
    pdf_storage_path TEXT,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS biomarkers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    panel_id UUID REFERENCES lab_panels(id) ON DELETE CASCADE,
    user_id INT NOT NULL,
    marker_name VARCHAR(100) NOT NULL,
    value NUMERIC(10,2) NOT NULL,
    unit VARCHAR(30),
    ref_range_min NUMERIC(10,2),
    ref_range_max NUMERIC(10,2),
    status VARCHAR(30) DEFAULT 'optimal',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS meals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INT NOT NULL,
    logged_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    meal_type VARCHAR(30),
    image_url TEXT,
    calories INT,
    protein_g NUMERIC(5,1),
    carbs_g NUMERIC(5,1),
    fat_g NUMERIC(5,1),
    quality_score INT,
    coach_notes TEXT
);

CREATE TABLE IF NOT EXISTS athlete_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    content_text TEXT NOT NULL,
    category VARCHAR(50),
    embedding vector(1536)
);

CREATE TABLE IF NOT EXISTS health_graph (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INT NOT NULL,
    source_node VARCHAR(100) NOT NULL,
    target_node VARCHAR(100) NOT NULL,
    relationship_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
