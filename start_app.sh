#!/bin/bash

# Configuration
DAEMON_PORT=8000
VOICEVOX_PORT=50021

echo "🚀 Starting Reachy Mini Driving Assistant..."

# 1. Check Voicevox
echo "Checking Voicevox..."
if ! curl -s "http://localhost:$VOICEVOX_PORT/version" > /dev/null; then
    echo "❌ Voicevox is NOT running on port $VOICEVOX_PORT."
    echo "Please start Voicevox engine first."
    exit 1
fi
echo "✅ Voicevox is running."

# 2. Start Reachy Mini Daemon
echo "Starting Reachy Mini Daemon..."
# Check if already running
if lsof -i :$DAEMON_PORT > /dev/null; then
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
    trap "echo 'Stopping daemon...'; kill $DAEMON_PID" EXIT
fi

# 3. Run Main App
echo "Starting Main Application..."
python main.py
