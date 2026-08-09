# Multi-Source Health Data Deduplication & Live HealthKit Architecture Design Specification

## Overview
This specification details the technical architecture for:
1. **Live Apple HealthKit Integration**: Configuring native iOS HealthKit entitlements (`NSHealthShareUsageDescription`, `NSHealthUpdateUsageDescription`) in `app.json` and querying live HealthKit biometrics on physical iPhones with simulator fallback.
2. **Multi-Source Data Deduplication & Priority Hierarchy (`app/health_hub/deduplication_service.py`)**: Matching duplicate workouts across Garmin, Strava, and Apple HealthKit within $\pm 5$ minutes and $\pm 5\%$ distance, setting native recording sources as primary, and resolving metric conflicts.
3. **Source Badging & User Device Preferences**: Displaying transparent source badges on activity/recovery cards and offering primary device selection in user profile settings.

---

## 1. Live Apple HealthKit Entitlements (`gymbro-frontend-expo/app.json`, `app/services/healthkit.ts`)

### 1.1 iOS Info.plist Usage Descriptions
Add `NSHealthShareUsageDescription` and `NSHealthUpdateUsageDescription` to `app.json` under `expo.ios.infoPlist`:
```json
{
  "expo": {
    "ios": {
      "infoPlist": {
        "NSHealthShareUsageDescription": "GYMBro reads your Apple Health Resting HR, Sleep, and HRV data to personalize your AI Coach advice.",
        "NSHealthUpdateUsageDescription": "GYMBro syncs health metrics to build your unified fitness dashboard."
      }
    }
  }
}
```

### 1.2 Native & Simulator Execution
- **Physical iOS**: Requests permissions for Resting HR, Sleep, HRV, Steps, and Active Energy.
- **Simulator / Fallback**: Returns realistic mock biometrics if native HealthKit permissions are unavailable.

---

## 2. Multi-Source Data Deduplication Engine (`app/health_hub/deduplication_service.py`)

### 2.1 Workout Deduplication Logic
- **Time Window Matching**: Activities occurring within $\pm 5$ minutes of start time with similar duration ($\pm 5\%$) or distance ($\pm 5\%$) are grouped as duplicates.
- **Primary Source Selection**:
  - `Garmin Connect (Native FIT file)` $>$ `Strava API` $>$ `Apple HealthKit` $>$ `In-App Manual`.
  - The highest-priority match is marked `is_primary = True`, while duplicate records store `duplicate_source_ids`.

### 2.2 Biometrics & Recovery Priority Hierarchy
- **Resting HR, HRV & Sleep**: `Garmin / Apple HealthKit (Continuous Wearables)` $>$ `In-App Manual`.
- **Steps & Active Calories**: Deduplicate steps from phone + watch by adopting the designated primary wearable's daily total.

---

## 3. Source Badging & User Preferences

### 3.1 Visual Source Badging
- Dashboard activity and recovery cards render clean badges (`⌚ Garmin (Primary)`, `🍎 Apple Health`, `🔥 Strava`).

### 3.2 Athlete Device Settings
- Allows users to configure their preferred primary device for Workouts and Biometrics in Profile settings.
