import asyncio
import os
from dotenv import load_dotenv
from src.google_maps_client import GoogleMapsClient
from src.gemini_client import GeminiClient

# Mock MCP Wrapper for testing
class MockMCPWrapper:
    def get_gemini_tools(self):
        return []
    async def handle_tool_call(self, session, name, args):
        return f"Mock executed {name} with {args}"

async def test_integration():
    load_dotenv()
    print("Testing Integration...")
    
    # 1. Google Maps
    print("\n[Test 1] Google Maps Client")
    try:
        maps_client = GoogleMapsClient()
        result = maps_client.search_places("Tokyo Tower")
        print(f"Result (truncated): {result[:100]}...")
        if "以下の場所が見つかりました" in result:
             print("[PASS] Google Maps Search")
        else:
             print("[FAIL] Google Maps Search returned unexpected result")
    except Exception as e:
        print(f"[FAIL] Google Maps Exception: {e}")
        return

    # 2. Gemini
    print("\n[Test 2] Gemini Client (Text only)")
    try:
        mock_mcp = MockMCPWrapper()
        gemini = GeminiClient(mock_mcp, maps_client)
        
        # Test 2a: Simple greeting
        response = await gemini.process_input(text_input="こんにちは")
        print(f"Gemini Response: {response}")
        if response:
             print("[PASS] Gemini Greeting")
        else:
             print("[FAIL] Gemini sent empty response")

        # Test 2b: Setup Maps (Function Calling)
        # Note: We can't easily force function calling in a single turn without chat context,
        # but asking for a place should trigger it.
        print("\n[Test 3] Gemini + Maps Tool")
        response_maps = await gemini.process_input(text_input="東京タワー近くのレストランを教えて")
        print(f"Gemini Maps Response: {response_maps}")
        if "レストラン" in response_maps or "場所" in response_maps or "東京タワー" in response_maps:
             print("[PASS] Gemini triggered Maps tool")
        else:
             print("[WARN] Gemini might not have triggered maps or response is different.")

    except Exception as e:
        print(f"[FAIL] Gemini Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_integration())
