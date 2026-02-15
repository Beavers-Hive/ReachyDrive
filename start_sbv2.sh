#!/bin/bash

# Configuration
SBV2_DIR="Style-Bert-VITS2"
VENV_DIR="sbv2_venv"
PORT=10000

cd "$(dirname "$0")/$SBV2_DIR" || exit 1

# Activate venv
source "$VENV_DIR/bin/activate"

echo "🚀 Starting Style-Bert-VITS2 Server on port $PORT..."
# Using --port if supported, otherwise defaulting
# server_fastapi.py usually takes arguments
python server_fastapi.py
