import os
import json
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("websocket_server")

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"Client disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: str):
        logger.info(f"Broadcasting message: {message[:100]}...")
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error sending message: {e}")
                # We might want to remove dead connections here, but disconnect() handles explicit close
                
    async def broadcast_json(self, data: dict):
        await self.broadcast(json.dumps(data, ensure_ascii=False))

manager = ConnectionManager()

@app.get("/")
async def get():
    return {"status": "ok", "message": "WebSocket Server is running"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # We expect the robot to send data, and we broadcast it to everyone (the app)
            # The app might also send data later, so we just broadcast everything for now.
            data = await websocket.receive_text()
            
            # Try to parse as JSON just to log/validate, but we pass it as is or re-serialize
            try:
                json_data = json.loads(data)
                logger.info(f"Received: {json_data.get('type', 'unknown')}")
                # Re-broadcast to all clients (including the sender, which is fine, or filter if needed)
                await manager.broadcast_json(json_data)
            except json.JSONDecodeError:
                logger.warning("Received non-JSON content")
                await manager.broadcast(data)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)
