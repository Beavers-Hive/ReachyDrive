import asyncio
import os
import logging
import traceback
import json
from google import genai
from google.genai import types
from google.genai.types import Tool, FunctionDeclaration, Schema, Type

from .google_maps_client import GoogleMapsClient, get_tool_declaration as get_maps_tool
from .mcp_client_wrapper import ReachyMCPWrapper
from .voicevox_client import VoicevoxClient
from PIL import Image
import io
import re # Added for sentence splitting
from .websocket_client import ReachyWebSocketClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GeminiLiveClient:
    def __init__(self, mcp_wrapper: ReachyMCPWrapper, maps_client: GoogleMapsClient, voicevox_client: VoicevoxClient, reachy_io):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
             raise ValueError("GEMINI_API_KEY not found")
        # Try v1beta which usually has the latest stable-ish models
        self.client = genai.Client(api_key=self.api_key, http_options={"api_version": "v1beta"})
        self.model_id = "gemini-2.0-flash" 

        self.mcp_wrapper = mcp_wrapper
        self.maps_client = maps_client
        self.voicevox_client = voicevox_client
        self.voicevox_client = voicevox_client
        self.reachy_io = reachy_io
        
        # WebSocket Client
        self.ws_uri = os.getenv("WEBSOCKET_URL", "ws://localhost:8080/ws")
        self.ws_client = ReachyWebSocketClient(self.ws_uri)
        self.ws_started = False
        
        self._is_periodic_active = False # Flag to pause audio input
        self._startup_done = False # Flag to prevent re-greeting on reconnect
        
        # Audio output queue for Voicevox
        self._audio_queue = asyncio.Queue()
        self._text_buffer = "" # RAW buffer from API
        self._speech_buffer = "" # Buffer for text inside <speech> tags
        self._is_inside_speech = False
        
        self.sys_instruction = """
あなたは Reachy Mini という名前の、親切でフレンドリーな運転席の助手ロボットです。
ユーザー（ドライバー）と楽しく会話をしてください。

【重要ルール】
1. 回答は **すべて日本語のみ** で行ってください。
2. **毎回の発言で必ず** expressEmotion（感情表現）を使ってください。嬉しい時はhappy、驚いた時はsurprised、考え中はcurious、など。
3. 挨拶や重要な場面では performGesture（ジェスチャー）も使ってください。
4. あなたの声は別のシステム（VOICEVOX）で生成されるため、ハキハキと日本語で話してください。
5. 会話が途切れたら、checkCamera を呼び出して周囲の景色を確認し、話題にしてください。
6. 時々 checkDriver を呼び出して、ドライバーの状態を確認してください。眠そうなら注意喚起してください。
"""

    def _get_tools(self):
        maps_tool = get_maps_tool()
        mcp_tools = self.mcp_wrapper.get_gemini_tools()
        
        # Camera tools - model can call these to see the environment
        camera_tools = Tool(function_declarations=[
            FunctionDeclaration(
                name="checkCamera",
                description="Check the front-facing camera to see the scenery and surroundings. Use this to find conversation topics about the environment.",
                parameters=Schema(
                    type=Type.OBJECT,
                    properties={},
                )
            ),
            FunctionDeclaration(
                name="checkDriver",
                description="Check the driver-facing camera to see the driver's condition. Use this to check if the driver looks tired or sleepy.",
                parameters=Schema(
                    type=Type.OBJECT,
                    properties={},
                )
            )
        ])
        
        return [maps_tool, camera_tools] + mcp_tools

    async def run(self, mcp_session):
        """
        Main loop for the Live API session with auto-reconnect on server errors.
        """
        # Using Gemini 2.5 Flash Native Audio with Output Transcription for VOICEVOX integration.
        session_model_id = "gemini-2.5-flash-native-audio-preview-12-2025"
        
        config = {
            "response_modalities": ["AUDIO"],
            "output_audio_transcription": {},
            "tools": self._get_tools(),
            "system_instruction": types.Content(parts=[types.Part(text=self.sys_instruction)]),
        }

        max_retries = 10
        retry_count = 0
        base_wait = 2.0  # seconds

        while retry_count < max_retries:
            try:
                async with self.client.aio.live.connect(model=session_model_id, config=config) as session:
                    logger.info(f"Connected to Gemini Live API with model: {session_model_id} (attempt {retry_count + 1})")
                    
                    # Start WebSocket Client in background if not already started
                    if not self.ws_started:
                        self.ws_client.start_in_background(asyncio.get_running_loop())
                        self.ws_started = True
                    
                    # Reset retry count on successful connection
                    retry_count = 0
                    
                    # Start Input Task (Microphone -> Gemini)
                    input_task = asyncio.create_task(self._send_audio_input(session))
                    
                    # Start Audio Output Task (Voicevox queue -> Speaker)
                    output_worker = asyncio.create_task(self._audio_output_worker())
                    
                    # Start Periodic Tasks
                    periodic_task = asyncio.create_task(self._periodic_tasks(session, mcp_session))
                    
                    # Start Output Task (Gemini -> Speaker & Tools)
                    try:
                        self._text_buffer = ""
                        self._speech_buffer = ""
                        self._is_inside_speech = False
                        
                        while True:
                            async for response in session.receive():
                                if response.server_content:
                                    # 1. Handle Tool Calls / Thoughts
                                    model_turn = response.server_content.model_turn
                                    if model_turn:
                                        for part in model_turn.parts:
                                            if part.text:
                                                logger.debug(f"Model Thought: {part.text}")
                                            if part.inline_data:
                                                pass

                                    # 2. Handle Output Transcription (Actual Japanese speech)
                                    if response.server_content.output_transcription:
                                        transcript_text = response.server_content.output_transcription.text
                                        if transcript_text:
                                            logger.info(f"Transcript (Japanese): {transcript_text}")
                                            await self._process_text_part(transcript_text)
                                    
                                    # 3. Check if turn is finished to flush remaining text
                                    if response.server_content.turn_complete:
                                        if self._text_buffer.strip():
                                            await self._synthesize_and_queue(self._text_buffer.strip())
                                        self._text_buffer = ""

                                if response.tool_call:
                                     await self._handle_tool_calls(session, response.tool_call, mcp_session)

                    except asyncio.CancelledError:
                        return  # Clean shutdown, don't retry
                    except Exception as e:
                        logger.error(f"Live Session Error: {e}")
                        traceback.print_exc()
                    finally:
                        input_task.cancel()
                        periodic_task.cancel()
                        output_worker.cancel()

            except asyncio.CancelledError:
                return  # Clean shutdown
            except Exception as e:
                logger.error(f"Connection Error: {e}")
                traceback.print_exc()

            # Auto-reconnect with exponential backoff
            retry_count += 1
            wait_time = min(base_wait * (2 ** (retry_count - 1)), 30.0)
            logger.warning(f"Session disconnected. Reconnecting in {wait_time:.1f}s... (attempt {retry_count}/{max_retries})")
            await asyncio.sleep(wait_time)

        logger.error(f"Max retries ({max_retries}) reached. Stopping.")

    async def _send_audio_input(self, session):
        """
        Reads audio from ReachyIO and sends to Gemini.
        """
        try:
            # We need an iterator from reachy_io that yields bytes
            async for audio_chunk in self.reachy_io.audio_input_generator():
                if self._is_periodic_active:
                    continue # Skip while sending image/text to avoid interweaving
                await session.send_realtime_input(
                    audio=types.Blob(data=audio_chunk, mime_type="audio/pcm")
                )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Audio Input Error: {e}")

    async def _process_text_part(self, text: str):
        """
        Buffers transcript text and splits into sentences for Voicevox synthesis.
        Allows English proper nouns if they appear within Japanese context.
        """
        self._text_buffer += text
        
        # Split by sentence delimiters: 。！？!?  \n
        sentences = re.split(r'([。！？!?\n])', self._text_buffer)
        
        # If we have at least one complete sentence
        if len(sentences) > 1:
            # Reconstruct sentences
            complete_sentences = []
            for i in range(0, len(sentences) - 1, 2):
                s = sentences[i] + sentences[i+1]
                if s.strip():
                    complete_sentences.append(s.strip())
            
            # The last element is the remaining partial sentence
            self._text_buffer = sentences[-1]
            
            # Synthesize each complete sentence
            for s in complete_sentences:
                # Filter: Only synthesize if it contains Japanese characters
                # or is part of a Japanese interaction.
                # We allow letters, numbers and punctuation if Japanese is present.
                if re.search(r'[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf]', s):
                     # DO NOT strip English proper nouns anymore. 
                     # Just trim leading/trailing whitespace.
                     clean_text = s.strip()
                     if clean_text:
                        asyncio.create_task(self._synthesize_and_queue(clean_text))

    async def _synthesize_and_queue(self, text: str):
        """
        Synthesizes text using Voicevox and puts into audio playback queue.
        """
        logger.info(f"Synthesizing sentence: {text}")
        audio_data = await self.voicevox_client.generate_audio_async(text)
        if audio_data:
            # Strip WAV header (44 bytes) for streaming playback if reachy_io expects raw PCM
            # But search_places and voicevox outputs are standard wav.
            # ReachyIO.play_stream_chunk expects PCM 16bit 24kHz.
            # Voicevox default is often 24kHz or 48kHz.
            # Let's check voicevox_client            # Voicevox default is often 24kHz or 48kHz.
            # ReachyIO.play_stream_chunk needs to be robust.
            await self._audio_queue.put(audio_data)
            
            # Send to WebSocket
            await self.ws_client.send_text_event(text, speaker="robot")

    async def _audio_output_worker(self):
        """
        Consumes audio from queue and plays it.
        """
        try:
            while True:
                audio_data = await self._audio_queue.get()
                # Use a more high-level playback that handles WAV/headers if needed
                # reachy_io.play_audio is sync and blocking, but we want to play
                # in a way that doesn't block the loop.
                # Actually, reachy_io.play_stream_chunk takes raw bytes and queues them.
                # We need to strip the header if it's there.
                
                if audio_data.startswith(b'RIFF'):
                    # Strip 44 bytes header
                    raw_pcm = audio_data[44:]
                    self.reachy_io.play_stream_chunk(raw_pcm)
                else:
                    self.reachy_io.play_stream_chunk(audio_data)
                
                self._audio_queue.task_done()
        except asyncio.CancelledError:
            pass

    async def _handle_tool_calls(self, session, tool_call, mcp_session):
        """
        Executes tools and sends results back to Gemini.
        """
        tool_outputs = []
        
        for call in tool_call.function_calls:
            name = call.name
            args = call.args
            logger.info(f"Tool Call: {name} args={args}")
            
            result = None
            
            # Google Maps
            if name == "searchPlaces":
                result, places = self.maps_client.search_places(
                    query=args.get("query"),
                    location=args.get("location")
                )
                # Send locations to WebSocket
                if places:
                    for place in places:
                        await self.ws_client.send_location_event(
                            name=place.get("name"),
                            address=place.get("address")
                        )
            
            # Camera Tools
            elif name == "checkCamera":
                result = await self._analyze_camera("front")
            elif name == "checkDriver":
                result = await self._analyze_camera("driver")
            
            # MCP Tools
            elif name in ["expressEmotion", "performGesture", "lookAtDirection", "nodHead", "shakeHead"]:
                if mcp_session:
                    asyncio.create_task(self.mcp_wrapper.handle_tool_call(mcp_session, name, args))
                    result = "Action started."
                else:
                    result = "MCP Session not active."
            else:
                result = f"Tool {name} not found."

            tool_outputs.append(
                types.FunctionResponse(
                    name=name,
                    response={"result": result},
                    id=call.id
                )
            )

        # Send tool response
        if tool_outputs:
            await session.send_tool_response(function_responses=tool_outputs)

    async def _analyze_camera(self, camera_type="front", mime_type="image/jpeg"):
        """
        Captures and analyzes a camera image using generateContent (gemini-2.0-flash).
        Returns the analysis text as a tool response string.
        Called by checkCamera/checkDriver tool handlers.
        """
        try:
            frame = self.reachy_io.get_latest_frame()
            if not frame:
                return "カメラ画像を取得できませんでした。"
            
            logger.info(f"Analyzing {camera_type} camera image ({len(frame)} bytes)...")
            
            if camera_type == "driver":
                prompt = "この画像にはドライバーが写っています。ドライバーの表情や姿勢を日本語で2〜3文で簡潔に説明してください。眠そうかどうかも判断してください。マークダウンは使わないでください。"
            else:
                prompt = "この画像に何が写っているか、日本語で2〜3文で簡潔に説明してください。マークダウンは使わないでください。"
            
            response = await self.client.aio.models.generate_content(
                model=self.model_id,  # gemini-2.0-flash
                contents=[
                    types.Part(inline_data=types.Blob(data=frame, mime_type=mime_type)),
                    types.Part(text=prompt)
                ]
            )
            
            analysis = response.text if response.text else "画像の分析ができませんでした。"
            # Clean up markdown
            analysis = analysis.replace("**", "").replace("*", "").replace("#", "").strip()
            if len(analysis) > 300:
                analysis = analysis[:300]
            logger.info(f"Camera analysis result: {analysis}")
            return analysis
            
        except Exception as e:
            logger.error(f"Camera analysis error: {e}")
            return f"カメラ分析中にエラーが発生しました: {str(e)}"

    async def _speak_image_analysis(self, image_bytes, prompt_text, mime_type="image/jpeg"):
        """
        Analyzes an image with generateContent and speaks the result
        directly via VOICEVOX. Does NOT touch the Live API session.
        """
        if not image_bytes:
            return
        
        self._is_periodic_active = True
        logger.info(f"Periodic image analysis: pausing audio input...")
        
        try:
            logger.info(f"Analyzing image ({len(image_bytes)} bytes) via generateContent...")
            response = await self.client.aio.models.generate_content(
                model=self.model_id,  # gemini-2.0-flash
                contents=[
                    types.Part(inline_data=types.Blob(data=image_bytes, mime_type=mime_type)),
                    types.Part(text=prompt_text)
                ]
            )
            spoken_text = response.text if response.text else None
            if spoken_text:
                spoken_text = spoken_text.replace("**", "").replace("*", "").replace("#", "").strip()
                if len(spoken_text) > 200:
                    spoken_text = spoken_text[:200]
                logger.info(f"Periodic speech: {spoken_text}")
                await self._synthesize_and_queue(spoken_text)
            else:
                logger.warning("No response from periodic image analysis")
        except Exception as e:
            logger.error(f"Periodic image analysis error: {e}")
            traceback.print_exc()
        finally:
            self._is_periodic_active = False
            logger.info("Periodic image analysis finished: resuming audio input.")

    async def _look_around(self, mcp_session):
        """
        Look around in all directions: left → right → up → down → forward.
        """
        if not mcp_session:
            logger.warning("MCP Session not active for look around")
            return
        
        logger.info("Looking around...")
        movements = [
            {"yaw": 90, "duration": 1.5},    # Left
            {"yaw": -90, "duration": 1.5},    # Right
            {"pitch": 20, "duration": 1.0},   # Up
            {"pitch": -20, "duration": 1.0},  # Down
            {"yaw": 0, "pitch": 0, "duration": 1.5},  # Forward (reset)
        ]
        for move in movements:
            await self.mcp_wrapper.handle_tool_call(mcp_session, "moveHead", move)
            await asyncio.sleep(2.0)
        logger.info("Look around complete.")

    async def _periodic_tasks(self, session, mcp_session):
        """
        Runs periodic tasks:
        - Startup: Look around (left, right, up, down, forward)
        - Every 120s: Environment check (look around + front camera) → speak via VOICEVOX
        - Every 60s: Driver check (head rotation + driver camera) → speak via VOICEVOX
        """
        print("Starting Periodic Tasks (env: 2min / driver: 1min)...")
        
        # Startup: Look around and greet (only on first launch)
        if not self._startup_done:
            logger.info("Startup: Looking around to survey environment...")
            await self._look_around(mcp_session)
            
            logger.info("Startup greeting...")
            await self._synthesize_and_queue("リーチーミニ、起動しました！お話ししましょう！")
            self._startup_done = True
        else:
            logger.info("Reconnected. Skipping startup greeting.")
        
        start_time = asyncio.get_running_loop().time()
        last_env_check = start_time
        last_driver_check = start_time + 30  # Offset to avoid collision
        
        INTERVAL_ENV = 120     # 2 minutes
        INTERVAL_DRIVER = 60   # 1 minute
        
        try:
            while True:
                await asyncio.sleep(1.0)
                current_time = asyncio.get_running_loop().time()
                
                # Skip checks while speaking (audio queue has items)
                if not self._audio_queue.empty() or self._is_periodic_active:
                    continue
                
                # Environment Check (every 2min): Look around + front camera scenery
                if current_time - last_env_check >= INTERVAL_ENV:
                    logger.info("Periodic: Environment Check")
                    last_env_check = current_time
                    
                    # Look around first
                    await self._look_around(mcp_session)
                    
                    # Then capture front view and analyze
                    frame = self.reachy_io.get_latest_frame()
                    await self._speak_image_analysis(
                        frame,
                        "あなたは運転席のアシスタントロボットです。この画像は車の前方カメラの映像です。「承知しました」「はい」などの前置きは絶対に言わないでください。最初の一文目から、見える景色について面白い発見や気づいたことを自然な話し言葉で2〜3文で話してください。例えば「あ、あそこに〜が見えますね！」のような感じです。マークダウンは使わないでください。"
                    )
                
                # Driver Check (every 60s): Head rotation + driver camera
                if current_time - last_driver_check >= INTERVAL_DRIVER:
                    logger.info("Periodic: Driver Check")
                    last_driver_check = current_time
                    
                    if mcp_session:
                        # 1. Look at driver (right side)
                        await self.mcp_wrapper.handle_tool_call(mcp_session, "moveHead", {"yaw": -90, "duration": 2.0})
                        await asyncio.sleep(2.5)
                        
                        # 2. Capture image
                        frame = self.reachy_io.get_latest_frame()
                        
                        # 3. Look back forward
                        await self.mcp_wrapper.handle_tool_call(mcp_session, "moveHead", {"yaw": 0, "duration": 2.0})
                        
                        # 4. Analyze and speak
                        await self._speak_image_analysis(
                            frame,
                            "あなたは運転席のアシスタントロボットです。この画像にはドライバーが写っています。ドライバーの様子を見て、眠そうなら注意喚起し、そうでなければ軽く気遣う言葉をかけてください。自然な話し言葉で2〜3文で話してください。マークダウンは使わないでください。"
                        )
                    else:
                        logger.warning("MCP Session not active for Driver Check")

        except asyncio.CancelledError:
            pass
