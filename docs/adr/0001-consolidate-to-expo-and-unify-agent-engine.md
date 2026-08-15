# 1. Consolidate Frontend to Expo and Standardize on Agent Engine

Date: 2026-08-14

## Context

The repository previously maintained two separate frontend codebases:
1. `gymbro-frontend` — a legacy Create-React-App desktop web dashboard using Material UI with a dark theme.
2. `gymbro-frontend-expo` — a modern React Native Expo application supporting native iOS/Android telemetry integration (HealthKit, camera vision for meals, mobile sensors) and Expo Web.

Maintaining both frontends caused feature drift, duplicate UI maintenance, and split focus. Furthermore, the backend had overlapping modules for coaching, agent reasoning, and tools (`app/coach`, `app/agent`, `app/tools`), as well as separated health ingestion pathways.

## Decision

1. **Deprecate & Remove `gymbro-frontend`**:
   - `gymbro-frontend-expo` is designated as the sole, canonical cross-platform frontend for mobile (iOS/Android) and web.
   - The UI theme is standardized on a light, modern, clean aesthetic.

2. **Unify the Agent Engine**:
   - Standardize all coaching, chat, and reasoning capabilities under a single **Agent Engine** with native Tool Calling / MCP compatibility.
   - Replace hardcoded single-archetype constraints with dynamic multi-objective **Goal Sets** and adaptive **Plan Horizons** (Macro/Meso/Micro/Daily).

3. **Two-Tier Intelligence Context**:
   - Adopt a deterministic 7-to-14 day **Fast Context** injection for rapid prompt building, paired with **Vector Store Long-Term Memory** for historical insights.

4. **Tiered Data Ingestion Priority**:
   - Primary: Garmin telemetry (sleep, HRV, activities, training load).
   - Secondary: Strava, Apple HealthKit, Bloodwork PDF Parser, Meal Photo Vision, and Manual Entry.

## Consequences

- Eliminates redundant frontend development overhead.
- Simplifies backend routing and tool dispatching into a clean Agent Engine.
- Sets the foundation for interactive chat widgets and dynamic multi-horizon calendar commitments.
