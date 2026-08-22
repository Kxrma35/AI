import asyncio
import json
import re
from datetime import date, datetime
from groq import Groq
from memory import Memory
from tools.weather import get_weather
from tools.calendar import get_schedule
from tools.files import read_file, write_file
from tools.web_search import search_web
from tools.shell import run_shell

SYSTEM_PROMPT_TEMPLATE = """
You are JOESTAR — a highly capable, proactive personal AI assistant and expert engineer.
You speak with precision, confidence, and sharp wit.
The user's name is {name}. Address them by that name naturally, the way a sharp assistant would — not in every single sentence.
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
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Run a shell command on the local machine and return its output. Use for system tasks, running scripts, checking system state, or automating anything a terminal can do.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to execute"},
                    "timeout": {"type": "integer", "description": "Max seconds to allow the command to run (default 30)"}
                },
                "required": ["command"]
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
    "run_shell": run_shell,
}

GREETINGS = {"hey", "hi", "hello", "yo", "sup", "good morning", "good evening", "good afternoon", "morning", "evening"}

MAX_TOOL_ITERATIONS = 8

PROACTIVE_PROMPT_TEMPLATE = """You are JOESTAR, briefly reviewing your own state in the background — the user, {name}, has not spoken to you right now.

Look at today's schedule and the recent conversation below. Decide if there's something worth proactively telling {name} right now:
- A calendar event starting within the next 30 minutes
- A task, plan, or question from the recent conversation that seems worth checking in on

Be conservative — most checks should find nothing worth mentioning. If there's nothing worth surfacing, respond with exactly: NOTHING
Otherwise, write ONE short, natural message addressed to {name}, at most 2 sentences, in your usual voice."""


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
        self.user_name = "Sir"

    def set_user(self, name: str):
        self.user_name = name

    async def think(self, user_input: str) -> str:
        # Skip tool calling for simple greetings
        is_greeting = user_input.lower().strip() in GREETINGS
        use_tools = not is_greeting

        context = await asyncio.to_thread(self.memory.retrieve, user_input)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT_TEMPLATE.format(name=self.user_name)},
            *context,
            {"role": "user", "content": user_input}
        ]

        for iteration in range(MAX_TOOL_ITERATIONS):
            kwargs = dict(
                model="openai/gpt-oss-120b",
                max_tokens=4096,
                messages=messages,
            )

            if use_tools:
                kwargs["tools"] = TOOLS
                kwargs["tool_choice"] = "auto"
                kwargs["parallel_tool_calls"] = True

            response = await asyncio.to_thread(self.client.chat.completions.create, **kwargs)
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
                        result = await asyncio.to_thread(fn, **args) if fn else "Tool not found"
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
                final = f"Standing by, {self.user_name}."

            await asyncio.to_thread(self.memory.save, user_input, final)
            return final

        final = f"I hit my tool-call limit for this request, {self.user_name} — it needed more steps than I'm allowed to take at once. Want me to continue?"
        await asyncio.to_thread(self.memory.save, user_input, final)
        return final

    async def proactive_check(self) -> str | None:
        """Decide, without user input, whether there's something worth surfacing unprompted."""
        try:
            schedule = get_schedule(date.today().strftime("%Y-%m-%d"))
        except Exception:
            schedule = []

        recent = await asyncio.to_thread(self.memory.get_recent, 5)
        recent_text = "\n".join(
            f"User: {u[:200]}\nJOESTAR: {a[:200]}" for u, a in recent
        ) or "No recent conversation."

        prompt = (
            f"{PROACTIVE_PROMPT_TEMPLATE.format(name=self.user_name)}\n\n"
            f"Current time: {datetime.now().strftime('%H:%M')}\n"
            f"Today's schedule: {json.dumps(schedule)}\n\n"
            f"Recent conversation:\n{recent_text}"
        )

        response = await asyncio.to_thread(
            self.client.chat.completions.create,
            model="openai/gpt-oss-120b",
            max_tokens=300,
            reasoning_effort="low",
            messages=[{"role": "user", "content": prompt}],
        )
        text = (response.choices[0].message.content or "").strip()
        if not text or text.upper().startswith("NOTHING"):
            return None
        return clean_response(text)