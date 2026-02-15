#!/bin/bash

# Configuration
DAEMON_PORT=8000
TTS_PORT=10000

echo "🚀 Starting Reachy Mini Driving Assistant..."

# 1. Start Style-Bert-VITS2
echo "Starting Style-Bert-VITS2..."
./start_sbv2.sh > sbv2.log 2>&1 &
TTS_PID=$!

echo "Waiting for TTS Server to be ready on port $TTS_PORT..."
# Check if running
MAX_RETRIES=60
count=0
while ! curl -s "http://localhost:$TTS_PORT/docs" > /dev/null; do
    sleep 2
    count=$((count+1))
    if [ $count -ge $MAX_RETRIES ]; then
        echo "❌ TTS Server failed to start."
        cat sbv2.log
        kill $TTS_PID
        exit 1
    fi
    echo -n "."
done
echo "✅ TTS Server is ready."

# 2. Start Reachy Mini Daemon
echo "Starting Reachy Mini Daemon..."
# Check if already running
if lsof -iTCP:$DAEMON_PORT -sTCP:LISTEN > /dev/null 2>&1; then
    echo "⚠️ Reachy Mini Daemon is already running on port $DAEMON_PORT."
    echo "Using existing daemon."
else
    # Find daemon executable
    # Assumes it's in path or in venv/bin
    DAEMON_CMD="reachy-mini-daemon"
    
    if ! command -v $DAEMON_CMD &> /dev/null; then
        echo "❌ $DAEMON_CMD not found in PATH."
        # Try to guess common location or fail
        # Miniconda path from verification: /opt/homebrew/Caskroom/miniconda/base/bin/reachy-mini-daemon
        DAEMON_CMD="/opt/homebrew/Caskroom/miniconda/base/bin/reachy-mini-daemon"
        if [ ! -f "$DAEMON_CMD" ]; then
             echo "❌ Could not find reachy-mini-daemon."
             exit 1
        fi
    fi

    echo "Running $DAEMON_CMD..."
    $DAEMON_CMD > daemon.log 2>&1 &
    DAEMON_PID=$!
    echo "Daemon started with PID $DAEMON_PID. Waiting for it to be ready..."
    
    # Wait for port 8000
    MAX_RETRIES=20
    count=0
    while ! lsof -i :$DAEMON_PORT > /dev/null; do
        sleep 1
        count=$((count+1))
        if [ $count -ge $MAX_RETRIES ]; then
            echo "❌ Timeout waiting for Reachy Mini Daemon."
            kill $DAEMON_PID
            exit 1
        fi
        echo -n "."
    done
    echo ""
    echo "✅ Reachy Mini Daemon is ready."
    
    # Cleanup trap
    trap "echo 'Stopping daemon...'; kill $DAEMON_PID $TTS_PID" EXIT
fi

# 3. Run Main App
echo "Starting Main Application..."
python main.py
