import requests
import aiohttp
import json
import os
import asyncio

class VoicevoxClient:
    def __init__(self, base_url: str = "http://localhost:50021", speaker_id: int = 1):
        self.base_url = base_url
        self.speaker_id = speaker_id

    def generate_audio(self, text: str) -> bytes:
        # Keeping existing sync method for potential compatibility
        # but adding async one for the Live client
        try:
             # Sync version
            query_payload = {"text": text, "speaker": self.speaker_id}
            query_response = requests.post(f"{self.base_url}/audio_query", params=query_payload)
            query_response.raise_for_status()
            query_data = query_response.json()
            synthesis_payload = {"speaker": self.speaker_id}
            synthesis_response = requests.post(
                f"{self.base_url}/synthesis",
                params=synthesis_payload,
                json=query_data
            )
            synthesis_response.raise_for_status()
            return synthesis_response.content
        except Exception as e:
            print(f"Voicevox API Error: {e}")
            return b""

    async def generate_audio_async(self, text: str) -> bytes:
        """
        Generate audio from text using Voicevox (Asynchronous).
        """
        if not text:
            return b""
            
        try:
            async with aiohttp.ClientSession() as session:
                # 1. Audio Query
                query_params = {"text": text, "speaker": self.speaker_id}
                async with session.post(f"{self.base_url}/audio_query", params=query_params) as resp:
                    resp.raise_for_status()
                    query_data = await resp.json()

                # 2. Synthesis
                synthesis_params = {"speaker": self.speaker_id}
                async with session.post(
                    f"{self.base_url}/synthesis",
                    params=synthesis_params,
                    json=query_data
                ) as resp:
                    resp.raise_for_status()
                    return await resp.read()

        except Exception as e:
            print(f"Voicevox Async API Error: {e}")
            return b""
