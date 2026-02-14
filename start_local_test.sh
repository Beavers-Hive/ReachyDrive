#!/bin/bash
# Local testing script

# Trap Ctrl+C to kill background processes
trap "kill 0" EXIT

echo "Starting Local WebSocket Server..."
cd server
uvicorn main:app --host 0.0.0.0 --port 8080 &
SERVER_PID=$!
cd ..

# Wait for server to start
sleep 3

echo "Starting Robot Client..."
export WEBSOCKET_URL="ws://localhost:8080/ws"
# Assuming python3 and dependencies are set
# Check if requirements need install
# pip install websockets

python3 src/gemini_live_client.py &
CLIENT_PID=$!

echo "Server (PID $SERVER_PID) and Client (PID $CLIENT_PID) are running."
echo "Press Ctrl+C to stop."

wait
