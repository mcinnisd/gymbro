# Apple HealthKit Integration, Rich Markdown Chat & Interactive Onboarding Widgets Design Specification

## Overview
This specification details the technical architecture and component design for:
1. **Apple HealthKit Sync & Non-Wearable Athlete Experience**: Auto-syncing iOS Apple Health data (Resting HR, Sleep, HRV, Steps, Active Energy) alongside manual baseline fallback inputs for athletes without wearables.
2. **Chat UI Polish & Rich Markdown Engine**: Fixing raw `**word**` text formatting using a custom React Native Markdown renderer, eliminating blank speech bubbles, and streaming tokens word-by-word via Server-Sent Events (SSE).
3. **Interactive Onboarding Widgets & Visual Training Charts**: Interactive day selection buckets (`[Mon] [Tue] [Wed]...`) inside the interview chat and dynamic visual bar charts previewing weekly volume and intensity.

---

## 1. Apple HealthKit Integration & Non-Wearable Baseline Engine (`gymbro-frontend-expo/app/services/healthkit.ts`)

### 1.1 Apple HealthKit Module
- **iOS Integration**: Native HealthKit module / `react-native-health` wrapper requesting read permissions for:
  - Resting Heart Rate (`HKQuantityTypeIdentifierRestingHeartRate`)
  - Sleep Analysis (`HKCategoryTypeIdentifierSleepAnalysis`)
  - Heart Rate Variability (`HKQuantityTypeIdentifierHeartRateVariabilitySDNN`)
  - Active Energy Burned (`HKQuantityTypeIdentifierActiveEnergyBurned`)
  - Step Count (`HKQuantityTypeIdentifierStepCount`)
- **Backend Sync**: Posts daily biometrics to `POST /health_hub/ingest_daily`.

### 1.2 Non-Wearable Athlete Experience
- **Step 1 Integration Card**: 3 distinct cards — **Apple HealthKit**, **Garmin/Strava**, and **Manual Baseline Entry**.
- **Manual Entry Fallback**: Provides numeric inputs for Age, Weight, Height, Average Sleep Hours, Resting HR, and Weekly Volume during Step 2 of onboarding.

---

## 2. Chat UI Rich Markdown Engine & Real-Time Token Streaming (`gymbro-frontend-expo/app/(tabs)/chat.tsx`, `components/MarkdownText.tsx`)

### 2.1 Rich Markdown Text Component (`gymbro-frontend-expo/app/components/MarkdownText.tsx`)
- Parses Markdown formatting strings into styled React Native elements:
  - `**bold text**` $\rightarrow$ `<Text style={{ fontWeight: 'bold', color: '#F8FAFC' }}>`
  - `*italic text*` $\rightarrow$ `<Text style={{ fontStyle: 'italic' }}>`
  - `### Heading` $\rightarrow$ `<Text style={{ fontSize: 16, fontWeight: 'bold', color: '#00E5FF', marginVertical: 4 }}>`
  - `- Bullet point` $\rightarrow$ Bullet row with dot icon
  - \`code\` $\rightarrow$ Monospace code container

### 2.2 Blank Speech Bubble Removal & Floating Status Indicator
- Removes `content: ''` `botPlaceholder` speech bubble creation.
- Displays floating status bar (`⚡ Coach Bro is calculating training zones...`) above the text input bar during AI inference.

### 2.3 Real-Time SSE Token Streaming
- Reads Server-Sent Events stream from `POST /chats/<id>/messages`.
- Appends incoming token chunks real-time to the active message content word-by-word.

---

## 3. Interactive Onboarding Widgets & Visual Training Volume Chart (`gymbro-frontend-expo/app/components/`)

### 3.1 Day Selector Widget (`gymbro-frontend-expo/app/components/DaySelectorWidget.tsx`)
- Interactive day selection pills: `[Mon] [Tue] [Wed] [Thu] [Fri] [Sat] [Sun]`.
- Tapping pills toggles active days and sends formatted schedule selection (e.g., *"I want to train on Mon, Wed, Fri"*) directly into the interview stream.

### 3.2 Dynamic Training Volume Bar Chart (`gymbro-frontend-expo/app/components/TrainingVolumeChart.tsx`)
- Rendered inside the *Interview Completed* summary card.
- Displays visual volume (km/miles) and workout intensity breakdown bars across the 7-day week before full calendar generation.
