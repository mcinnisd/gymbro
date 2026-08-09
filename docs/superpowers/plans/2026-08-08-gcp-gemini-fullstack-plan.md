# GCP & Gemini SDK Fullstack Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Google Cloud Storage (GCS) file upload service, Gemini 2.5 PDF lab bloodwork parser, Cloud Run production Docker container & deployment script, and a comprehensive GCP architectural educational guide in README.md.

**Architecture:** 
- `app/gcp/`: GCS file upload module (`storage_service.py`).
- `app/biomarkers/pdf_service.py`: `google.genai` multimodal PDF document parser.
- `app/biomarkers/routes.py`: `POST /biomarkers/upload-pdf` endpoint.
- `Dockerfile`: WSGI production container.
- `scripts/deploy_gcp.sh`: 1-command Cloud Run deployment script.
- `README.md`: GCP technical architecture educational deep-dive.

---

## Global Constraints

- **Python Unit test check**: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/ -v` must pass cleanly.
- **TypeScript check**: `cd gymbro-frontend-expo && npx tsc --noEmit` must pass with 0 errors.

---

### Task 1: GCS Storage Service & Gemini Lab PDF Parser (`app/gcp/`, `pdf_service.py`)

**Files:**
- Create: `app/gcp/__init__.py`
- Create: `app/gcp/storage_service.py`
- Create: `app/biomarkers/pdf_service.py`
- Modify: `app/biomarkers/routes.py`
- Test: `tests/unit/test_gcp_services.py`

- [ ] **Step 1: Write unit test for GCS storage and PDF parser**

Create `tests/unit/test_gcp_services.py` testing GCS upload fallback and Gemini PDF document parsing.

- [ ] **Step 2: Run test to verify failure**

Run: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/test_gcp_services.py -v`

- [ ] **Step 3: Write implementation**

Create `app/gcp/storage_service.py`, `app/biomarkers/pdf_service.py`, and register `POST /biomarkers/upload-pdf` in `app/biomarkers/routes.py`.

- [ ] **Step 4: Run test to verify pass**

Run: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/test_gcp_services.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/gcp/ app/biomarkers/pdf_service.py app/biomarkers/routes.py tests/unit/test_gcp_services.py
git commit -m "feat(gcp): implement GCS storage service and Gemini 2.5 PDF lab parser endpoint"
```

---

### Task 2: Production Dockerfile & Cloud Run Deployment Script (`Dockerfile`, `scripts/deploy_gcp.sh`)

**Files:**
- Create: `Dockerfile`
- Create: `scripts/deploy_gcp.sh`

- [ ] **Step 1: Create production `Dockerfile`**

Create Dockerfile based on `python:3.12-slim` running gunicorn server on port 5001 / PORT env.

- [ ] **Step 2: Create executable `scripts/deploy_gcp.sh`**

Add deployment script with `gcloud run deploy` command and `chmod +x`.

- [ ] **Step 3: Commit**

```bash
git add Dockerfile scripts/deploy_gcp.sh
git commit -m "feat(gcp): add production Dockerfile and 1-command Cloud Run deployment script"
```

---

### Task 3: GCP Architectural Educational Deep-Dive Guide in README (`README.md`)

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add comprehensive GCP Architecture Guide to `README.md`**

Document how GCP works, Vertex AI vs Gemini API key, Cloud Run serverless execution, GCS object storage, Secret Manager, IAM security, and fullstack deployment steps.

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add comprehensive GCP fullstack architecture educational guide to README.md"
```
