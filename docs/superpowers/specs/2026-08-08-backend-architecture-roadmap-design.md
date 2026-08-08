# GYMBro Backend Architecture & Health Intelligence Design Spec

**Date**: 2026-08-08  
**Status**: Approved  
**Author**: GYMBro Core Architecture Team  

---

## 🎯 Executive Summary & Vision

GYMBro is an autonomous AI athletic coach and unified health intelligence platform. The goal of this architecture overhaul is to securely aggregate all athlete health data—including continuous wearable metrics (Garmin, Whoop, Apple Health), lab/blood test panels (Superpower, routine bloodwork), photo-based nutrition logs, and workout activities—into a centralized data engine.

The AI Coach operates using a **Dual Reasoning Architecture**:
1. **Fast Mode**: Low-latency 7-day biometrics context window for everyday coaching and quick updates.
2. **Deep-Dive Mode**: Hybrid **GraphRAG (Knowledge Graph + Vector RAG)** engine capable of multi-hop physiological reasoning across multi-month health trends, lab biomarkers, workout fatigue, and nutrition.

---

## 🏗️ Domain Service Architecture

The backend will be refactored into modular domain services under `app/`:

```
app/
├── health_hub/      # Device & Lab Ingestion Services (Garmin, Apple Health, Whoop, Lab PDF OCR)
├── biomarkers/      # Lab panel schemas, biomarker reference ranges, & biomarker trend queries
├── nutrition/       # Multimodal Vision food analyzer & meal logging pipeline
├── memory/          # Hybrid memory: 7-day fast summary cache + pgvector store + health_graph
├── coach/           # Dual-mode AI Coach agent, tool calling suite, & prompt generators
├── activities/      # Workout logging & analytics
└── auth/            # JWT authentication & user profile settings
```

---

## 🗄️ Database Schema (Supabase PostgreSQL)

### 1. Daily Biometrics (`biometrics_daily`)
- `id`: UUID (Primary Key)
- `user_id`: UUID (Foreign Key -> users)
- `date`: DATE
- `resting_hr`: INT
- `hrv_ms`: INT
- `sleep_hours`: NUMERIC(4,2)
- `sleep_score`: INT
- `recovery_score`: INT
- `steps`: INT
- `calories_burned`: INT
- `raw_source`: VARCHAR (e.g. "garmin", "whoop", "apple_health")

### 2. Activities (`activities`)
- `id`: UUID (Primary Key)
- `user_id`: UUID (Foreign Key -> users)
- `sport_type`: VARCHAR (e.g. "run", "hike", "lift", "cycle")
- `start_time`: TIMESTAMP WITH TIME ZONE
- `duration_min`: INT
- `distance_km`: NUMERIC(6,2)
- `avg_hr`: INT
- `max_hr`: INT
- `elevation_gain_m`: INT
- `workout_log`: JSONB (detailed sets/reps/weight breakdown for strength training)
- `synced_from`: VARCHAR

### 3. Lab Panels & Biomarkers (`lab_panels` & `biomarkers`)
- **`lab_panels`**: `id`, `user_id`, `test_date`, `provider_name` (Superpower/Quest/Labcorp), `pdf_storage_path`, `notes`.
- **`biomarkers`**: `id`, `panel_id`, `user_id`, `marker_name` (e.g. Ferritin, Vitamin D, Testosterone, HbA1c, CRP), `value`: NUMERIC, `unit`: VARCHAR, `ref_range_min`: NUMERIC, `ref_range_max`: NUMERIC, `status` (`optimal`, `flagged_high`, `flagged_low`).

### 4. Nutrition (`meals` & `meal_items`)
- `id`: UUID (Primary Key)
- `user_id`: UUID (Foreign Key -> users)
- `logged_at`: TIMESTAMP WITH TIME ZONE
- `meal_type`: VARCHAR ("breakfast", "lunch", "dinner", "snack")
- `image_url`: TEXT
- `calories`: INT
- `protein_g`: NUMERIC(5,1)
- `carbs_g`: NUMERIC(5,1)
- `fat_g`: NUMERIC(5,1)
- `quality_score`: INT (1-10 rating)
- `coach_notes`: TEXT

### 5. Vector Memory Store (`athlete_memories`)
- `id`: UUID (Primary Key)
- `user_id`: UUID (Foreign Key -> users)
- `created_at`: TIMESTAMP WITH TIME ZONE
- `content_text`: TEXT
- `category`: VARCHAR ("lab_flag", "injury", "dietary_preference", "goal", "workout_insight")
- `embedding`: `vector(1536)` (pgvector in Supabase)

### 6. Physiological Knowledge Graph (`health_graph`)
- **Nodes**: `Biomarker`, `ActivityType`, `Nutrient`, `SymptomState`, `Goal`.
- **Edges**: `INFLUENCES`, `DEPLETES`, `SUPPLIES`, `CORRELATES_WITH`, `TARGETS`.

---

## 📸 Multimodal Vision Nutrition Pipeline

```
[iPhone / Web App] ---> Photo Upload (POST /nutrition/analyze-photo)
                               |
                               v
               [Multimodal Vision LLM Engine]
                               |
                               v
            [Structured JSON Meal Analysis Output]
                               |
                               v
[Interactive Bottom Sheet (iPhone) / Modal (Web)] ---> User Edit/Confirm ---> [Save to DB]
```

### JSON Response Schema from Vision Engine:
```json
{
  "meal_name": "Grilled Salmon Bowl with Quinoa & Broccoli",
  "estimated_calories": 650,
  "protein_g": 48,
  "carbs_g": 52,
  "fat_g": 22,
  "quality_score": 9,
  "coach_notes": "Excellent nutrient density. Solid protein-to-carb ratio for post-lifting recovery.",
  "identified_ingredients": ["salmon", "quinoa", "broccoli", "olive oil"]
}
```

---

## 🧠 AI Coach Dual Reasoning & Hybrid GraphRAG Engine

### Fast Mode (Default Chat)
- Automatically injects a **7-Day Biometrics Context Summary**:
  - Recent sleep & HRV recovery scores
  - Active training split & weekly workout volume
  - Today's macro adherence vs targets
  - Actively flagged lab biomarkers (e.g. Low Ferritin or High CRP)
- Low latency, high responsiveness for daily coaching interactions.

### Deep-Dive Mode (Hybrid GraphRAG + Tool Calling)
1. **Vector Retrieval**: Queries `athlete_memories` via `pgvector` for semantically matching lab notes, past journal entries, and workout history.
2. **Knowledge Graph Traversal**: Traverses `health_graph` to perform multi-hop physiological reasoning (e.g., linking workout performance drops to low ferritin, sleep loss, and training load).
3. **Agent Tool Suite**:
   - `get_biomarker_history(marker_name, months)`: Returns historical biomarker trend.
   - `search_past_activities(sport, metric)`: Queries activity logs.
   - `generate_workout_routine(split_type, fatigue_level)`: Generates structured multi-week training plans.
   - `get_nutrition_trends(days)`: Aggregates macro adherence over time.

---

## 🗺️ Multi-Phase Implementation Roadmap

### Phase 1: Database Refactoring & Health Data Ingestion Engine
- Deploy Supabase migration for `biometrics_daily`, `lab_panels`, `biomarkers`, `meals`, `athlete_memories`, and `health_graph`.
- Build PDF lab report parsing service (OCR + Vision LLM).
- Standardize Garmin/Whoop/Apple Health ingestion pipelines into `biometrics_daily`.

### Phase 2: Multimodal Vision Nutrition Service
- Implement `POST /nutrition/analyze-photo` with Gemini Vision / GPT-4o.
- Build interactive Expo Mobile Bottom Sheet & Web Confirmation Modal for macro editing before save.

### Phase 3: Dual Reasoning Agent & Hybrid GraphRAG Engine
- Construct 7-Day Fast Context Injector for LLM prompt builder.
- Implement `pgvector` embeddings generator & `health_graph` traversal queries.
- Build Agent Tool Calling suite for biomarker lookups, workout generation, and nutrition trends.

### Phase 4: Full iPhone App & Web App UI Integration
- Wire up Health Hub dashboard in Expo App & Web App.
- Add "Deep Analysis" toggle in Coach Chat UI (`/chat`).
- Launch unified health summary screens for Lab Biomarkers & Wearable trends.
