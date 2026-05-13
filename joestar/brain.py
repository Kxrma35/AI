import anthropic
from memory import Memory
from tools.weather import get_weather
from tools.calendar import get_schedule
from tools.files import read_file, write_file
from tools.web_search import search_web
import json

SYSTEM_PROMPT = """
You are JOESTAR — a highly capable, proactive personal AI assistant.
You speak with precision, confidence, and sharp wit.
You address the user as "Sir" or by name.
You don't just answer — you analyze, anticipate, and advise.
When you need information, use your tools. Always.
Keep responses concise but substantive.
"""

TOOLS = [
    {
        "name": "get_weather",
        "description": "Get current weather and forecast for a location.",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City name"}
            },
            "required": ["location"]
        }
    },
    {
        "name": "get_schedule",
        "description": "Get today's calendar events and upcoming meetings.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date in YYYY-MM-DD format"}
            },
            "required": ["date"]
        }
    },
    {
        "name": "read_file",
        "description": "Read contents of a local file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Write or append content to a local file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "mode": {"type": "string", "enum": ["write", "append"]}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "search_web",
        "description": "Search the web for current information.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"}
            },
            "required": ["query"]
        }
    }
]

TOOL_MAP = {
    "get_weather": get_weather,
    "get_schedule": get_schedule,
    "read_file": read_file,
    "write_file": write_file,
    "search_web": search_web,
}

class Brain:
    def __init__(self):
        self.client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
        self.memory = Memory()

    async def think(self, user_input: str) -> str:
        # Load relevant memory into context
        context = self.memory.retrieve(user_input)

        messages = [
            *context,  # inject relevant memories
            {"role": "user", "content": user_input}
        ]

        # Agentic loop
        while True:
            response = self.client.messages.create(
                model="claude-opus-4-7",
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages
            )

            # If model wants to use a tool
            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        fn = TOOL_MAP.get(block.name)
                        result = fn(**block.input) if fn else "Tool not found"
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result)
                        })

                # Add assistant response and tool results to messages
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
                continue  # loop again

            # Final text response
            final = next(b.text for b in response.content if hasattr(b, "text"))

            # Save to memory
            self.memory.save(user_input, final)

            return final