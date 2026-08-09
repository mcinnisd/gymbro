#!/usr/bin/env bash
set -e

# ==============================================================================
# 🚀 1-Command Google Cloud Run Deployment Script for GYMBro Backend
# ==============================================================================

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-gymbro-499418}"
REGION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
SERVICE_NAME="gymbro-backend"

echo "========================================================================"
echo "⚡ Deploying GYMBro Flask REST API to Google Cloud Run"
echo "   Project:  ${PROJECT_ID}"
echo "   Region:   ${REGION}"
echo "   Service:  ${SERVICE_NAME}"
echo "========================================================================"

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: Google Cloud SDK ('gcloud') is not installed on PATH."
    echo "   Install via: brew install --cask google-cloud-sdk"
    exit 1
fi

# Submit build & deploy container to Cloud Run
gcloud run deploy "${SERVICE_NAME}" \
    --source . \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --platform managed \
    --allow-unauthenticated \
    --port 5001 \
    --set-env-vars "FLASK_ENV=production,USE_VERTEX_AI=true,GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION}"

echo "========================================================================"
echo "✅ GYMBro Cloud Run Deployment Complete!"
echo "========================================================================"
