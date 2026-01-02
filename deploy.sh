#!/bin/bash
# Deployment script for qbToJson to Google Cloud Run
# Uses Cloud Build (--source) to avoid registry issues

set -e  # Exit on error

# Configuration
SERVICE_NAME="qbtojson"
REGION="us-central1"

echo "🚀 Deploying qbToJson to Google Cloud Run"
echo "=========================================="
echo "Service: ${SERVICE_NAME}"
echo "Region: ${REGION}"
echo "Method: Cloud Build (--source)"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: gcloud CLI not found. Please install Google Cloud SDK."
    exit 1
fi

# Check if logged in to gcloud
echo "📋 Checking gcloud authentication..."
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo "❌ Error: Not authenticated with gcloud. Run: gcloud auth login"
    exit 1
fi

# Deploy to Cloud Run using Cloud Build
echo ""
echo "🚀 Deploying to Cloud Run with Cloud Build..."
echo "   (This will build and deploy automatically)"
echo ""

gcloud run deploy ${SERVICE_NAME} \
  --source . \
  --region ${REGION} \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300s \
  --max-instances 10 \
  --min-instances 0

if [ $? -ne 0 ]; then
    echo "❌ Cloud Run deployment failed!"
    exit 1
fi

# Get the service URL
echo ""
echo "✅ Deployment successful!"
echo ""
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format 'value(status.url)')
echo "🌐 Service URL: ${SERVICE_URL}"
echo ""
echo "📋 Test the service:"
echo "   Health check: curl ${SERVICE_URL}/health"
echo "   API info: curl ${SERVICE_URL}/api/info"
echo ""
echo "🎉 Deployment complete!"
