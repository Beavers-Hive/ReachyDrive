#!/bin/bash

# Configuration
SBV2_DIR="Style-Bert-VITS2"
REPO_URL="https://github.com/litagin02/Style-Bert-VITS2.git"
VENV_DIR="sbv2_venv"

echo "🚀 Setting up Style-Bert-VITS2..."

# 1. Clone Repository
if [ ! -d "$SBV2_DIR" ]; then
    echo "Cloning repository..."
    git clone "$REPO_URL" "$SBV2_DIR"
else
    echo "Repository already exists."
fi

cd "$SBV2_DIR"

# 2. Create Virtual Environment
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

# 3. Install Dependencies
echo "Installing dependencies..."
# Upgrade pip
pip install --upgrade pip

# Install PyTorch (Mac friendly)
pip install torch torchaudio

# Install requirements
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
fi

# Force downgrade transformers for compatibility
pip install transformers==4.35.2

# 4. Download Default Model (jvnv-F1-jp)
MODEL_DIR="model_assets/jvnv-F1-jp"
if [ ! -d "$MODEL_DIR" ]; then
    echo "Downloading default model (jvnv-F1-jp)..."
    # Using python script in the repo if available, or manual download
    # Usually Style-Bert-VITS2 has a model downloader or we can fetch from HF
    
    # Create dir
    mkdir -p "$MODEL_DIR"
    
    # Download config.json, style_vectors.npy, safetensors from HuggingFace
    # URL: https://huggingface.co/litagin/Style-Bert-VITS2-JVNV/tree/main/jvnv-F1-jp
    
    BASE_URL="https://huggingface.co/litagin/Style-Bert-VITS2-JVNV/resolve/main/jvnv-F1-jp"
    
    curl -L "$BASE_URL/config.json" -o "$MODEL_DIR/config.json"
    curl -L "$BASE_URL/style_vectors.npy" -o "$MODEL_DIR/style_vectors.npy"
    curl -L "$BASE_URL/jvnv-F1-jp_e160_s14000.safetensors" -o "$MODEL_DIR/jvnv-F1-jp.safetensors"
    
    echo "Model downloaded."
else
    echo "Default model already exists."
fi

echo "✅ Style-Bert-VITS2 setup complete."
echo "To run server: ./server_fastapi.py"
