import asyncio
import os
import sys
from typing import List
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from google.genai.types import Tool, FunctionDeclaration, Schema, Type

class ReachyMCPWrapper:
    def __init__(self, repo_path: str = None):
        if repo_path is None:
            # Default to repo in the same root
            repo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reachy-mini-mcp")
        
        self.server_script = os.path.join(repo_path, "server.py")
        if not os.path.exists(self.server_script):
             raise FileNotFoundError(f"MCP server script not found at {self.server_script}")

        self.python_exe = sys.executable

    def get_server_params(self) -> StdioServerParameters:
        return StdioServerParameters(
            command=self.python_exe,
            args=[self.server_script],
            env=os.environ.copy() # Pass current env
        )

    def get_gemini_tools(self) -> List[Tool]:
        """
        Returns a list of Tool objects for Gemini.
        We map specific high-level actions to function declarations.
        """
        return [
            Tool(function_declarations=[
                FunctionDeclaration(
                    name="expressEmotion",
                    description="Make Reachy Mini express an emotion.",
                    parameters=Schema(
                        type=Type.OBJECT,
                        properties={
                            "emotion": Schema(
                                type=Type.STRING,
                                description="The emotion to express. Must be one of: happy, sad, curious, surprised, confused, neutral."
                            )
                        },
                        required=["emotion"]
                    )
                ),
                FunctionDeclaration(
                    name="performGesture",
                    description="Make Reachy Mini perform a gesture.",
                    parameters=Schema(
                        type=Type.OBJECT,
                        properties={
                            "gesture": Schema(
                                type=Type.STRING,
                                description="The gesture to perform. Must be one of: greeting, yes, no, thinking, celebration."
                            )
                        },
                        required=["gesture"]
                    )
                ),
                FunctionDeclaration(
                    name="lookAtDirection",
                    description="Make Reachy Mini look in a specific direction.",
                    parameters=Schema(
                        type=Type.OBJECT,
                        properties={
                            "direction": Schema(
                                type=Type.STRING,
                                description="The direction to look at. Must be one of: forward, up, down, left, right."
                            ),
                            "duration": Schema(
                                type=Type.NUMBER,
                                description="Duration of the movement in seconds. Default 1.0."
                            )
                        },
                        required=["direction"]
                    )
                ),
                FunctionDeclaration(
                    name="nodHead",
                    description="Make Reachy Mini nod its head (yes).",
                    parameters=Schema(
                        type=Type.OBJECT,
                        properties={},
                    )
                ),
                FunctionDeclaration(
                    name="shakeHead",
                    description="Make Reachy Mini shake its head (no).",
                    parameters=Schema(
                        type=Type.OBJECT,
                        properties={},
                    )
                )
            ])
        ]

    async def handle_tool_call(self, session: ClientSession, name: str, args: dict):
        """
        Executes the tool call by mapping it to the MCP 'operate_robot' tool.
        """
        print(f"Executing tool: {name} with args: {args}")
        
        mcp_tool_name = "operate_robot"
        mcp_args = {}

        if name == "expressEmotion":
            mcp_args = {
                "tool_name": "express_emotion",
                "parameters": {"emotion": args["emotion"]}
            }
        elif name == "performGesture":
            mcp_args = {
                "tool_name": "perform_gesture",
                "parameters": {"gesture": args["gesture"]}
            }
        elif name == "lookAtDirection":
            mcp_args = {
                "tool_name": "look_at_direction",
                "parameters": {"direction": args["direction"], "duration": args.get("duration", 1.0)}
            }
        elif name == "nodHead":
             mcp_args = {
                "tool_name": "nod_head",
                "parameters": {"duration": 2.0, "angle": 15}
            }
        elif name == "shakeHead":
             mcp_args = {
                "tool_name": "shake_head",
                "parameters": {"duration": 2.0, "angle": 15}
            }
        elif name == "moveHead":
            # Direct access to move_head
            mcp_args = {
                "tool_name": "move_head",
                "parameters": args
            }
        else:
            return f"Unknown tool: {name}"

        try:
            result = await session.call_tool(mcp_tool_name, arguments=mcp_args)
            return result
        except Exception as e:
            print(f"MCP Call Error: {e}")
            return str(e)

    async def execute_actions_sequence(self, session: ClientSession, actions: List[tuple]):
        """
        Executes a list of actions (name, args) sequentially with a small delay.
        """
        for name, args in actions:
            await self.handle_tool_call(session, name, args)
            # Add delay to prevent overwriting on the robot side if it checks too fast
            # Most gestures take 1-2 seconds.
            # Emotion is fast.
            delay = 2.0 
            if name == "expressEmotion":
                delay = 0.5
            elif name == "lookAtDirection":
                delay = args.get("duration", 1.0)
            
            await asyncio.sleep(delay)

from typing import List
