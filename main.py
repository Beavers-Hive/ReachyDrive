import asyncio
import os
import signal
import sys
from dotenv import load_dotenv

from src.gemini_live_client import GeminiLiveClient
from src.google_maps_client import GoogleMapsClient
from src.reachy_io_client import ReachyIOClient
from src.mcp_client_wrapper import ReachyMCPWrapper
from src.voicevox_client import VoicevoxClient
from src.ble_led_controller import BLELedController
from mcp import ClientSession
from mcp.client.stdio import stdio_client

# Load environment variables
load_dotenv()

async def main():
    print("Initializing Reachy Mini Driving Assistant (Live Mode)...")

    # Initialize Clients
    try:
        maps_client = GoogleMapsClient()
        print("Google Maps Client initialized.")
    except Exception as e:
        print(f"Failed to initialize Google Maps Client: {e}")
        return

    voicevox_client = VoicevoxClient()
    print("Voicevox Client initialized.")

    # Initialize Reachy IO
    reachy_io = ReachyIOClient()
    print("Reachy IO Client initialized.")

    # Initialize MCP Wrapper
    try:
        mcp_wrapper = ReachyMCPWrapper()
        print("Reachy MCP Wrapper initialized.")
    except Exception as e:
        print(f"Failed to initialize Reachy MCP Wrapper: {e}")
        return
        return

    # Initialize BLE LED Controller
    led_controller = BLELedController()
    led_controller.start()
    print("BLE LED Controller started.")

    # Initialize Gemini Live Client
    try:
        gemini_client = GeminiLiveClient(mcp_wrapper, maps_client, voicevox_client, reachy_io, led_controller)
        print("Gemini Live Client initialized.")
    except Exception as e:
        print(f"Failed to initialize Gemini Client: {e}")
        return
    
    server_params = mcp_wrapper.get_server_params()

    print("Connecting to MCP Server...")
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("Connected to MCP Server.")
            print("Ready to chat! (Live Mode - Break interrupt supported)")

            # Start Live Session
            await gemini_client.run(session)
            
    # Cleanup
    led_controller.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
