# GYMBro

GYMBro is an autonomous AI athletic coach and personal fitness tracking system. It integrates workout data, nutrition logging, daily recovery journals, and health metrics (Strava/Garmin) to deliver personalized summaries, workout recommendations, and interactive AI coaching.

---

## 🚀 Quick Start Guide

### Prerequisites
- **Python**: 3.10+
- **Node.js**: v18+ & `npm`
- **Expo Go App**: Download on your iPhone/iOS or Android device from the App Store.

---

### 1. Environment Setup

Create a `.env` file in the root directory (or use `.env.example` if available):

```env
FLASK_ENV=development
SECRET_KEY=your_secret_key
JWT_SECRET_KEY=your_jwt_secret_key
MOCK_DB=true  # Set to true for offline local testing, or false to use Supabase

# LLM Configuration
LLM_PROVIDER=gemini  # 'gemini', 'openai', 'xai', or 'local'
GEMINI_API_KEY=your_gemini_api_key

# Supabase (Optional if MOCK_DB=false)
SUPABASE_URL=https://your-supabase-url.supabase.co
SUPABASE_KEY=your_supabase_anon_key
```

---

### 2. Start the Backend API (Flask)

Open a terminal in the root directory (`gymbro`):

```bash
# Activate your Python virtual environment
source venv/bin/activate

# Install dependencies if needed
pip install -r requirements.txt

# Start the Flask backend server (listens on 0.0.0.0:5001)
python app.py
```

*The server will start at `http://0.0.0.0:5001`, accepting connections from both `localhost` and your local Wi-Fi network.*

---

### 3. Run the Mobile App on iPhone / Local Device (Expo)

Open a **second terminal** window and navigate to `gymbro-frontend-expo`:

```bash
cd gymbro-frontend-expo

# Install dependencies (first time setup)
npm install

# Start the Expo bundler
npx expo start
```

#### Connecting your iPhone:
1. Ensure your iPhone and laptop are connected to the **same Wi-Fi network**.
2. Open the **Camera app** on your iPhone and scan the **QR code** displayed in the terminal.
3. Tap **Open in "Expo Go"**.
4. The mobile app automatically detects your host computer's IP address (`http://<YOUR_LAPTOP_IP>:5001`) via Expo's `hostUri`.

> 💡 **Tip / Troubleshooting**: If connection fails due to local network isolation, tap the **Gear icon (🔧)** on the mobile app login screen to manually input your laptop's local IP (e.g. `http://192.168.1.50:5001`). To find your laptop's local IP on macOS: `ipconfig getifaddr en0`.
>
> For public Wi-Fi networks that block local device communication, run Expo in tunnel mode:
> ```bash
> npx expo start --tunnel
> ```

---

### 4. Run the Web App (React Desktop)

Open a **third terminal** (if using the web interface):

```bash
cd gymbro-frontend

# Install dependencies
npm install

# Start React web dev server
npm start
```

*The web application will open at `http://localhost:3000`.*

---

## 🏗️ Architecture Overview

- **Backend (`/app`)**: Flask REST API providing `/auth`, `/coach`, `/chats`, `/activities`, `/nutrition`, `/journal`, `/analytics`, `/strava`, and `/garmin` endpoints.
- **Mobile Frontend (`/gymbro-frontend-expo`)**: React Native app with Expo Router (`/training`, `/chat`, `/stats`, `/recovery`, `/nutrition`).
- **Web Frontend (`/gymbro-frontend`)**: React + MUI web dashboard.
- **AI Engine (`app/coach` & `app/agent`)**: Dynamic context builder & prompt generator interfacing with LLM providers to deliver autonomous fitness coaching.

---

## 🗺️ Project Roadmap

1. Clean up the repo and make it more organized <-- Check
2. Get a simple local website up and running with user logins <-- Check
   - a. Clean up website
   - b. Troubleshoot errors with pages <-- Check
   - c. Make sure all pages load requests from backend <-- Check
   - d. Make chatbot page and infrastructure <-- Check
3. Develop visualizations of user data (Number one priority)
   - a. Put data on website dashboard & mobile app
   - b. Clean up data structure storage and processing
4. Summarize gathered data and build v0 of the AI trainer
5. Implement trends and cleaner summarized information
6. Take into account user goals and preferences
7. Track workouts and recommend future workouts
8. Develop personalized plans for users
9. Track food and diet along with providing advice/recommendations
10. Memory integration to handle food dislikes and allergies
11. Mobile App (Expo / React Native) development <-- In Progress
12. Cloud deployment and server hosting <-- In Progress

---

## ☁️ Google Cloud Platform (GCP) & Gemini SDK Fullstack Architecture

This section serves as a technical knowledge base and architecture deep-dive for GYMBro's fullstack integration with **Google Cloud Platform (GCP)** and the **Google GenAI SDK (`google.genai`)**.

### 1. Architectural Component Map

```
                     ┌─────────────────────────────────────────┐
                     │          Expo Mobile App (iOS)          │
                     └────────────────────┬────────────────────┘
                                          │  REST API Calls
                                          ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                            Google Cloud Run                                  │
│             Serverless Container: gunicorn (app.py : 5001)                   │
├─────────────────────────────────────────┬────────────────────────────────────┤
│   Google GenAI SDK (google.genai)       │   Google Cloud Storage (GCS)       │
│  - gemini-2.5-flash (AI Coach Chat)     │   gs://gymbro-health-uploads       │
│  - gemini-2.5-flash (Meal Vision)       │   - Food Photos                    │
│  - gemini-2.5-flash (PDF Lab Parser)    │   - Bloodwork Lab PDFs             │
│  - text-embedding-004 (768-dim Vector)  │   - Avatars                        │
└─────────────────────────────────────────┴────────────────────────────────────┘
```

---

### 2. Deep-Dive: How GCP Services Work in GYMBro

#### A. Google GenAI SDK (`google.genai`) & Vertex AI
- **What it is**: The official unified Python client library (`from google import genai`) connecting to Google's Gemini models.
- **Vertex AI vs. Standalone API Key**:
  - *Gemini API Key*: Direct access using an API key (`GEMINI_API_KEY`). Best for fast prototyping and local testing.
  - *Vertex AI (`vertexai=True`)*: Enterprise mode using GCP IAM service accounts, project IDs (`gymbro-499418`), and regional endpoints (`us-central1`). Recommended for production workloads.
- **Multimodal Document & Vision Parsing**:
  - Gemini 2.5 Flash natively accepts raw PDF bytes and image byte streams (`google.genai.types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")`).
  - It extracts structured JSON without relying on legacy OCR engines (Tesseract).

#### B. Google Cloud Storage (GCS)
- **What it is**: Scalable, high-durability object storage for binary files (images, PDFs, documents).
- **How GYMBro uses GCS**:
  - When users upload food photos or blood test PDFs in the Expo app, the backend calls `upload_file_to_gcs(file_bytes, filename)` in `app/gcp/storage_service.py`.
  - Files are stored under `gs://gymbro-health-uploads/user_<id>/...` and served over HTTPS CDN URLs (`https://storage.googleapis.com/...`).

#### C. Google Cloud Run (Serverless Container Platform)
- **What it is**: Fully managed serverless execution platform that automatically scales Docker containers from zero to high concurrency.
- **Container Build & Deployment (`scripts/deploy_gcp.sh`)**:
  - GYMBro includes a production `Dockerfile` based on `python:3.12-slim` running `gunicorn`.
  - Deployment is triggered via 1 CLI command:
    ```bash
    ./scripts/deploy_gcp.sh
    ```
  - Cloud Run provisions HTTPS endpoints automatically with zero infrastructure management.

---

### 3. Deploying GYMBro to Google Cloud

1. **Install & Authenticate GCP CLI**:
   ```bash
   brew install --cask google-cloud-sdk
   gcloud auth login
   gcloud config set project gymbro-499418
   ```

2. **Deploy Backend Container to Cloud Run**:
   ```bash
   ./scripts/deploy_gcp.sh
   ```

3. **Verify Deployment**:
   ```bash
   curl https://gymbro-backend-us-central1.a.run.app/routes
   ```



