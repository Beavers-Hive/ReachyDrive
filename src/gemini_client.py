import os
import io
import asyncio
import logging
from google import genai
from google.genai import types
from .google_maps_client import GoogleMapsClient, get_tool_declaration as get_maps_tool
from .mcp_client_wrapper import ReachyMCPWrapper

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self, mcp_wrapper: ReachyMCPWrapper, maps_client: GoogleMapsClient):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
             raise ValueError("GEMINI_API_KEY not found")
        
        self.client = genai.Client(api_key=self.api_key)
        self.model_id = "gemini-2.5-flash"
        self.mcp_wrapper = mcp_wrapper
        self.maps_client = maps_client
        self.chat_session = None
        self.sys_instruction = """
You are Reachy Mini, a helpful and friendly driving assistant robot.
You are helping the driver with navigation and casual conversation.
Your responses should be spoken (short, conversational, Japanese).

IMPORTANT: You must ALWAYS perform a physical action (gesture or emotion) with EVERY response to show you are alive and listening.
- Use `express_emotion` (happy, sad, angry, surprised) to match the tone.
- Use `perform_gesture` (greeting, nod, shake_head, thinking, etc.) to emphasize your speech.
- Use `look_at_direction` to interact with the environment.
- NEVER respond with just text. ALWAYS pair text with a tool call.

You can search specifically for places using Google Maps.
If the user asks for a place, use the search_places tool.

Always be polite and helpful.
Do NOT output markdown formatting like **bold** in your speech text, as it will be read by TTS.
IMPORTANT: Output ONLY Japanese text for the speech. Do NOT include Romanized Japanese (Romaji) or English translations in the response text (unless specifically asked for English).
"""

    def _get_tools(self):
        maps_tool = get_maps_tool()
        mcp_tools = self.mcp_wrapper.get_gemini_tools()
        return [maps_tool] + mcp_tools

    def initialize_chat(self):
        tools = self._get_tools()
        self.chat_session = self.client.chats.create(
            model=self.model_id,
            config=types.GenerateContentConfig(
                tools=tools,
                system_instruction=self.sys_instruction,
                temperature=0.7,
            )
        )

    async def _execute_actions_background(self, mcp_session, action_list):
        """
        Execute actions sequentially in background to prevent overwriting.
        """
        for name, args in action_list:
            try:
                logger.info(f"Background execution: {name}")
                await self.mcp_wrapper.handle_tool_call(mcp_session, name, args)
                # Small delay to ensure command is registered/started ?? 
                # Ideally MCP wrapper waits for 'done' but if not, we might need sleep.
                # Assuming handle_tool_call awaits completion.
            except Exception as e:
                logger.error(f"Background action failed: {e}")

    async def process_input(self, text_input: str = None, audio_input: bytes = None, mcp_session=None) -> tuple[str, list]:
        """
        Process user input (text or audio) and return (response_text, action_list).
        """
        if not self.chat_session:
            self.initialize_chat()

        content = []
        if text_input:
            content.append(text_input)
        if audio_input:
            # Assume 16kHz mono WAV/PCM
             content.append(types.Part.from_bytes(data=audio_input, mime_type="audio/wav"))

        if not content:
            return "", []

        current_content = content
        
        # Accumulate all actions from all turns in this interaction?
        # Usually Gemini does one turn of tool calls then text.
        # But if it does multiple, we should probably execute all?
        # Let's accumulate.
        all_actions = []

        while True:
            try:
                # Synchronous call wrapped in async function (blocking)
                response = self.chat_session.send_message(current_content)
                
                if not response:
                    logger.error("Gemini returned None response.")
                    return "すみません、エラーが発生しました。", []
                
                # Check safeguards
                if not response.candidates:
                    logger.warning("Gemini returned no candidates (Safety block?).")
                    logger.warning(f"Finish Reason: {response.candidates[0].finish_reason if response.candidates else 'Unknown'}")
                    return "すみません、応答できませんでした。", []

                logger.info(f"Gemini Response Candidates: {len(response.candidates)}")
                # 1. Check for text response first
                if response.text:
                    logger.info(f"Gemini returned text: {response.text[:50]}...")
                    # Return accumulated actions too
                    return response.text, all_actions
                
                # 2. Check for function calls
                function_calls = response.function_calls
                logger.info(f"Function Calls: {function_calls}")
                
                if not function_calls:
                    # No text and no function calls?
                    # Check parts manually
                    try:
                        parts = response.candidates[0].content.parts
                        if parts:
                            for part in parts:
                                if part.text:
                                    return part.text, all_actions
                    except Exception as e:
                        logger.error(f"Error parsing response parts: {e}")
                    
                    # If we got here, we have empty response
                    return "", []

                # 3. Execute tools
                tool_outputs = []
                
                for call in function_calls:
                    name = call.name
                    args = call.args
                    
                    logger.info(f"Executing tool: {name} with args: {args}")
                    result = None
                    
                    # Google Maps (Blocking - we need the info)
                    if name == "search_places":
                        result = self.maps_client.search_places(
                            query=args.get("query"),
                            location=args.get("location")
                        )
                        tool_outputs.append(
                            types.Part.from_function_response(
                                name=name,
                                response={"result": result}
                            )
                        )
                    
                    # MCP Tools (Action/Motion)
                    elif name in ["express_emotion", "perform_gesture", "look_at_direction", "nod_head", "shake_head"]:
                        if mcp_session:
                            # Queue for execution (accumulate)
                            # all_actions is defined in outer scope
                            all_actions.append((name, args))
                            # Return success to continue to text gen
                            result = "Action scheduled." 
                        else:
                            result = "MCP Session not active."
                            
                        tool_outputs.append(
                            types.Part.from_function_response(
                                name=name,
                                response={"result": result}
                            )
                        )
                    
                    else:
                        result = f"Tool {name} not found."
                        tool_outputs.append(
                            types.Part.from_function_response(
                                name=name,
                                response={"result": result}
                            )
                        )

                # Fire off background actions - NO, returning them to main loop
                # if action_calls and mcp_session:
                #     asyncio.create_task(self._execute_actions_background(mcp_session, action_calls))
                
                # Send outputs back to model to get final response
                # IMPORTANT: We must update current_content to be the function response
                current_content = tool_outputs
                # The loop continues to call send_message with the function response
                
            except Exception as e:
                logger.error(f"Gemini Processing Error: {e}")
                import traceback
                traceback.print_exc()
                return "すみません、システムエラーが発生しました。", []
