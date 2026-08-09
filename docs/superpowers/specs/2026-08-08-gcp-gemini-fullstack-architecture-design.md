# Google Cloud Platform (GCP) & Gemini SDK Fullstack Architecture Design Specification

## Overview
This specification details the fullstack transition of **GYMBro** to the **Google Cloud Platform (GCP)** and **Google GenAI SDK (`google.genai`)**. It integrates Google Gemini 2.5 Flash for AI coaching, multimodal vision meal scanning, and PDF lab blood test document extraction, Google Cloud Storage (GCS) for cloud file persistence, and Google Cloud Run for serverless backend deployment.

---

## 1. Gemini 2.5 SDK AI & Multimodal Engine (`app/utils/llm_utils.py`, `app/nutrition/vision_service.py`, `app/biomarkers/pdf_service.py`)

### 1.1 Official Google GenAI SDK (`google.genai`)
- **SDK Import**: `from google import genai as google_genai`
- **Vertex AI Client**: Supports both Vertex AI authentication (`vertexai=True`, `project=Config.GOOGLE_CLOUD_PROJECT`, `location=Config.GOOGLE_CLOUD_LOCATION`) and standalone `GEMINI_API_KEY`.
- **Primary Models**:
  - `gemini-2.5-flash` / `gemini-2.0-flash` for low-latency AI Coach chat, 7-day fast context summaries, and dual reasoning tool calls.
  - `gemini-2.5-flash` for Multimodal Vision food photo analysis (calories, protein, carbs, fat, quality score).
  - `text-embedding-004` (768-dim) for fast vector embeddings stored in Supabase `pgvector` (`athlete_memories`).

### 1.2 Lab Blood Test PDF Document Parser (`app/biomarkers/pdf_service.py`)
- Accepts PDF document bytes or GCS URI and calls `google.genai` document parsing to extract lab blood test markers (Ferritin, CRP, Vitamin D, Testosterone, Lipid Panel) with reference range evaluations (`optimal`, `flagged_low`, `flagged_high`).

---

## 2. Google Cloud Storage (GCS) File Integration (`app/gcp/storage_service.py`)

### 2.1 Bucket Persistence
- GCS Service module (`upload_file_to_gcs`) uploads user food photos, lab blood test PDFs, and profile avatars to Google Cloud Storage (`gs://gymbro-health-uploads/user_<id>/...`).
- Returns secure GCS public/signed URLs for frontend rendering.
- Includes local storage fallback if GCP credentials are not enabled.

---

## 3. Google Cloud Run Serverless Deployment (`Dockerfile`, `scripts/deploy_gcp.sh`)

### 3.1 Production Docker Container
- Lightweight `Dockerfile` based on `python:3.12-slim` running `gunicorn` WSGI web server.

### 3.2 1-Command GCP Deployment Script (`scripts/deploy_gcp.sh`)
- Builds and deploys backend container to Google Cloud Run:
  ```bash
  gcloud run deploy gymbro-backend \
    --project=gymbro-499418 \
    --region=us-central1 \
    --allow-unauthenticated
  ```

---

## 4. Comprehensive GCP Technical Educational README Guide (`README.md`)
- Comprehensive educational section added to [README.md](file:///Users/davidmcinnis/codes/gymbro/README.md) explaining how GCP services work (Google GenAI SDK, Vertex AI, Cloud Run serverless container lifecycle, GCS object storage, Secret Manager, IAM roles).
