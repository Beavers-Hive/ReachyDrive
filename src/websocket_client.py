import asyncio
import websockets
import json
import logging
import threading

logger = logging.getLogger(__name__)

class ReachyWebSocketClient:
    def __init__(self, uri: str):
        self.uri = uri
        self.websocket = None
        self.running = False
        self._send_queue = asyncio.Queue()
        self._loop = None

    async def connect(self):
        """
        Connects to the WebSocket server and keeps the connection alive.
        """
        self.running = True
        while self.running:
            try:
                logger.info(f"Connecting to WebSocket server at {self.uri}...")
                async with websockets.connect(self.uri) as websocket:
                    self.websocket = websocket
                    logger.info("Connected to WebSocket server")
                    
                    # Consumer/Producer loop
                    consumer_task = asyncio.create_task(self._consumer_handler(websocket))
                    producer_task = asyncio.create_task(self._producer_handler(websocket))
                    
                    done, pending = await asyncio.wait(
                        [consumer_task, producer_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    
                    for task in pending:
                        task.cancel()
                        
            except Exception as e:
                logger.error(f"WebSocket connection error: {e}")
                self.websocket = None
                await asyncio.sleep(5) # Retry delay

    async def _consumer_handler(self, websocket):
        try:
            async for message in websocket:
                # We might receive ping/pong or other messages, currently we just log
                # logger.debug(f"Received from WS: {message}")
                pass
        except Exception:
            pass

    async def _producer_handler(self, websocket):
        while True:
            message = await self._send_queue.get()
            try:
                await websocket.send(message)
                logger.debug(f"Sent to WS: {message}")
            except Exception as e:
                logger.error(f"Error sending to WS: {e}")
                # Put back in queue? Or just drop to avoid blocking? 
                # For realtime status, dropping old messages is probably better than blocking.
            finally:
                self._send_queue.task_done()

    async def send_text_event(self, text: str, speaker: str = "robot"):
        """
        Send a text event (speech) to the server.
        """
        data = {
            "type": "text",
            "speaker": speaker, # "robot" or "user"
            "content": text,
            "timestamp": asyncio.get_running_loop().time()
        }
        await self._send_queue.put(json.dumps(data, ensure_ascii=False))

    async def send_location_event(self, name: str, address: str = ""):
        """
        Send a location event (map) to the server.
        """
        data = {
            "type": "location",
            "name": name,
            "address": address,
            "query": f"{name} {address}".strip(),
            "timestamp": asyncio.get_running_loop().time()
        }
        await self._send_queue.put(json.dumps(data, ensure_ascii=False))
        
    def start_in_background(self, loop):
        """
        Helper to start the connection loop in the background.
        """
        self._loop = loop
        loop.create_task(self.connect())

