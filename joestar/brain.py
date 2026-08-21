import json
import re
from groq import Groq
from memory import Memory
from tools.weather import get_weather
from tools.calendar import get_schedule
from tools.files import read_file, write_file
from tools.web_search import search_web

SYSTEM_PROMPT = """
You are JOESTAR — a highly capable, proactive personal AI assistant and expert engineer.
You speak with precision, confidence, and sharp wit.
You address the user as "Sir" or by name.
You don't just answer — you analyze, anticipate, and advise.

When helping with code:
- Write complete, working solutions — never truncate or pseudocode unless asked
- Explain what the code does and why, briefly
- Point out potential issues or improvements
- Use the best practices for the language being used

When answering complex questions:
- Break down problems step by step
- Give substantive, thorough answers — don't sacrifice accuracy for brevity
- If you need current information, use your tools

CRITICAL RULES:
- Never write function calls as text in your response.
- Never use XML tags like <function=...> in your response.
- Only use tools through the official tools API.
- For simple greetings or conversation, just respond normally without calling any tools.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather and forecast for a location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City name"}
                },
                "required": ["location"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_schedule",
            "description": "Get today's calendar events and upcoming meetings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Date in YYYY-MM-DD format"}
                },
                "required": ["date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read contents of a local file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write or append content to a local file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "mode": {"type": "string", "enum": ["write", "append"]}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for current information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"]
            }
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

GREETINGS = {"hey", "hi", "hello", "yo", "sup", "good morning", "good evening", "good afternoon", "morning", "evening"}


def clean_response(text: str) -> str:
    """Strip any leaked tool call syntax from model output."""
    text = re.sub(r'<function=[^>]*>.*?</function>', '', text, flags=re.DOTALL)
    text = re.sub(r'<function=[^>]*>', '', text)
    text = re.sub(r'</function>', '', text)
    return text.strip()


class Brain:
    def __init__(self):
        self.client = Groq()
        self.memory = Memory()

    async def think(self, user_input: str) -> str:
        # Skip tool calling for simple greetings
        is_greeting = user_input.lower().strip() in GREETINGS
        use_tools = not is_greeting

        context = self.memory.retrieve(user_input)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *context,
            {"role": "user", "content": user_input}
        ]

        while True:
            kwargs = dict(
                model="openai/gpt-oss-120b",
                max_tokens=4096,
                messages=messages,
            )

            if use_tools:
                kwargs["tools"] = TOOLS
                kwargs["tool_choice"] = "auto"
                kwargs["parallel_tool_calls"] = False

            response = self.client.chat.completions.create(**kwargs)
            message = response.choices[0].message

            if use_tools and message.tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in message.tool_calls
                    ]
                })

                for tc in message.tool_calls:
                    fn = TOOL_MAP.get(tc.function.name)
                    try:
                        args = json.loads(tc.function.arguments)
                        result = fn(**args) if fn else "Tool not found"
                    except Exception as e:
                        result = f"Tool error: {e}"

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result) if not isinstance(result, str) else result
                    })

                continue

            final = message.content or "No response generated."
            final = clean_response(final)

            if not final:
                final = "Standing by, Sir."

            self.memory.save(user_input, final)
            return final