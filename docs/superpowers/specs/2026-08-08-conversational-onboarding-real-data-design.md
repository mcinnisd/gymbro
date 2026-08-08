# Conversational Onboarding & Real-Data Engine Design Specification

## Overview
This specification outlines the redesign of the GYMBro onboarding flow into a simple, chat-first experience with AI Coach Bro. It purges all hardcoded/fake dummy data across the app and replaces missing data states with actionable 1-tap empty-state cards.

---

## 1. Conversational Chat Onboarding Flow (`app/coach/` & `gymbro-frontend-expo/app/(tabs)/chat.tsx`)

### 1.1 Direct Chat Intake
Upon registration, new users bypass complex static forms and enter directly into an interactive intake session with Coach Bro.

### 1.2 Broad Goal Archetype Classifier
Coach Bro prompts: *"What is your primary health & fitness goal right now?"* and presents quick-reply chips:
1. 🏋️ **Build Muscle & Strength** (Hypertrophy, progressive overload, protein targets)
2. 🔥 **Fat Loss & Recomposition** (Caloric deficit management, Zone 2 movement)
3. 🏃 **Endurance & Speed PRs** (Running, Cycling, Swimming volume, race tapers)
4. 🌿 **Longevity & Daily Energy** (Sleep optimization, daily steps, metabolic health)
5. ✍️ **Custom Goal (Free Response)** (Plain English input parsed by LLM reasoning, e.g. *"ACL rehab + return to rec basketball"*)

### 1.3 Device & Health Data Integration Intake
Coach Bro checks connected accounts and presents inline 1-tap connection cards:
- **Connect Garmin**
- **Connect Strava**
- **Upload Blood Test PDF**
- *"Skip for now / Do this later"*

---

## 2. Real-Data Engine & Actionable Empty States

### 2.1 Complete Dummy Data Purge
- Remove hardcoded default values across the app (such as mock sleep scores of 82/100, hardcoded 7-day RHR arrays `[62, 60, ...]`, and mock lab markers).
- All screens fetch authentic data from Supabase backend services.

### 2.2 Actionable Empty State Cards

#### Recovery / Health Hub Tab (`gymbro-frontend-expo/app/(tabs)/recovery.tsx`)
- **If Wearable Not Connected**: Render *"No Wearable Synced"* card with a **"⌚ Sync Garmin / Apple Health"** button.
- **If Bloodwork Not Uploaded**: Render *"No Bloodwork Analyzed"* card with an **"📤 Upload Lab PDF"** button.
- **If No Wearable Sleep/RHR Recorded Today**: Render clear prompt to log today's check-in or sync device.

#### Nutrition Tab (`gymbro-frontend-expo/app/(tabs)/nutrition.tsx`)
- Displays actual logged calories & macros.
- **If No Meals Logged Today**: Render *"No Meals Logged Today"* banner with a **"📸 Scan Meal Photo"** button.

#### Training Tab (`gymbro-frontend-expo/app/(tabs)/training.tsx`)
- Displays user's actual workout plan.
- **If No Workout Plan Generated**: Render *"No Active Workout Routine"* banner with a **"💬 Chat with Coach Bro"** button.
