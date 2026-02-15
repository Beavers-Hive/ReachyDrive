import requests
import aiohttp
import json
import os
import asyncio

class VoicevoxClient:
    def __init__(self, base_url: str = "http://localhost:10000", speaker_id: int = 0, speed_scale: float = 1.0, model_name: str = "Anneli", style: str = "通常"):
        self.base_url = base_url
        self.speaker_id = speaker_id
        self.speed_scale = speed_scale
        self.model_name = model_name
        self.style = style

    def generate_audio(self, text: str) -> bytes:
        try:
            # Style-Bert-VITS2 uses 'length' for duration (inverse of speed)
            length = 1.0 / self.speed_scale if self.speed_scale > 0 else 1.0
            
            params = {
                "text": text,
                "speaker_id": self.speaker_id,
                "model_name": self.model_name,
                "style": self.style,
                "length": length,
                "encoding": "utf-8"
            }
            # The server recommends POST for /voice
            response = requests.post(f"{self.base_url}/voice", params=params)
            response.raise_for_status()
            return response.content
        except Exception as e:
            print(f"Style-Bert-VITS2 API Error: {e}")
            return b""

    async def generate_audio_async(self, text: str) -> bytes:
        """
        Generate audio from text using Style-Bert-VITS2 (Asynchronous).
        """
        if not text:
            return b""
            
        try:
            # Style-Bert-VITS2 uses 'length' for duration (inverse of speed)
            length = 1.0 / self.speed_scale if self.speed_scale > 0 else 1.0
            
            async with aiohttp.ClientSession() as session:
                params = {
                    "text": text,
                    "speaker_id": self.speaker_id,
                    "model_name": self.model_name,
                    "style": self.style,
                    "length": length,
                    "encoding": "utf-8"
                }
                async with session.post(f"{self.base_url}/voice", params=params) as resp:
                    resp.raise_for_status()
                    return await resp.read()

        except Exception as e:
            print(f"Style-Bert-VITS2 Async API Error: {e}")
            return b""
