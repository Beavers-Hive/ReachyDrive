#!/bin/bash
# Helper script to build and deploy the server
# Usage: ./deploy_server.sh [PROJECT_ID] [SERVICE_NAME]

PROJECT_ID=$1
SERVICE_NAME=${2:-reachy-monitor-server}

if [ -z "$PROJECT_ID" ]; then
  echo "Usage: ./deploy_server.sh [PROJECT_ID] [SERVICE_NAME]"
  echo "Please provide your Google Cloud Project ID."
  exit 1
fi

echo "Deploying to Cloud Run in project: $PROJECT_ID..."

# Change to the directory where this script is located (server/)
cd "$(dirname "$0")"

gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME . --project $PROJECT_ID
gcloud run deploy $SERVICE_NAME --image gcr.io/$PROJECT_ID/$SERVICE_NAME --platform managed --region asia-northeast1 --allow-unauthenticated --project $PROJECT_ID
