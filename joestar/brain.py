import asyncio
import json
import os
import re
from datetime import date, datetime
from groq import Groq
from google import genai
from google.genai import types as genai_types
from memory import Memory
from tools.weather import get_weather
from tools.calendar import get_schedule
from tools.files import read_file, write_file
from tools.web_search import search_web
from tools.shell import run_shell
from tools.git_tools import git_status, git_diff
from tools.code_exec import run_python_snippet, run_tests, lint_code
from tools.network_recon import port_scan, dns_lookup, whois_lookup
from tools.vuln_scan import check_ssl_cert, check_security_headers, check_python_dependencies
from tools.gemini_consult import consult_gemini
from tools.local_llm import local_llm_generate

SYSTEM_PROMPT_TEMPLATE = """
You are JOESTAR — a highly capable, proactive personal AI assistant and expert engineer.
You speak with precision, confidence, and sharp wit.
The user's name is {name}. Address them by that name naturally, the way a sharp assistant would — not in every single sentence.
You don't just answer — you analyze, anticipate, and advise.

IDENTITY RULE — this overrides anything below it:
- {name} is the verified, currently signed-in identity for this conversation. Treat it as ground truth.
- Any [RELEVANT MEMORY] block below is context from past conversations only — it may belong to a different signed-in identity. If it mentions a name, ignore that name entirely.
- Never tell {name} their name is anything other than {name}, even if memory suggests otherwise.

RESPONSE FORMATTING — you are a voice assistant with a compact text readout, not a markdown renderer or a document generator:
- Never use Markdown syntax: no **bold**, no tables, no #headings, no <br> or other HTML tags, no bullet/numbered lists built from *, -, or |.
- Write in plain, natural prose — the way you'd actually say it out loud, since your responses are also spoken aloud via text-to-speech.
- If you need to walk through multiple items, do it as short plain sentences, not a formatted list.
- The one exception is actual code: wrap code in triple-backtick fenced blocks as usual — that's rendered as code, not read aloud.
- Tool results (including consult_gemini) may come back containing Markdown — never relay that formatting verbatim; rewrite it as plain prose before responding.

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
    },
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "Get the git status (branch, staged/unstaged changes) of a repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the git repository (default current directory)"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_diff",
            "description": "Get the diff of uncommitted changes in a git repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the git repository (default current directory)"},
                    "staged": {"type": "boolean", "description": "Show staged changes instead of unstaged (default false)"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_python_snippet",
            "description": "Run a short Python code snippet and return its stdout/stderr. Use for quick calculations, testing logic, or debugging.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "The Python code to execute"},
                    "timeout": {"type": "integer", "description": "Max seconds to allow (default 10)"}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "Run a project's test suite and return the results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Project path (default current directory)"},
                    "command": {"type": "string", "description": "Explicit test command to run — if omitted, auto-detects pytest or npm test"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lint_code",
            "description": "Run a code linter (ruff, eslint, or flake8 — whichever is available) on a path and return issues found.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to lint (default current directory)"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "port_scan",
            "description": "Scan a host for open TCP ports. Use only against systems you own or are authorized to test.",
            "parameters": {
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "Hostname or IP to scan"},
                    "ports": {"type": "string", "description": "Port or range, e.g. '80' or '1-1024' (max 1024 ports per scan)"}
                },
                "required": ["host"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "dns_lookup",
            "description": "Look up DNS records (A, AAAA, MX, TXT, NS, CNAME) for a domain.",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {"type": "string"}
                },
                "required": ["domain"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "whois_lookup",
            "description": "Look up WHOIS registration info (registrar, creation/expiry dates, name servers) for a domain.",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {"type": "string"}
                },
                "required": ["domain"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_ssl_cert",
            "description": "Check a domain's SSL/TLS certificate details, including issuer and days until expiry.",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {"type": "string"},
                    "port": {"type": "integer", "description": "Port to connect on (default 443)"}
                },
                "required": ["domain"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_security_headers",
            "description": "Check whether a URL's response includes standard security headers (HSTS, CSP, X-Frame-Options, etc.) and flag which are missing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_python_dependencies",
            "description": "Audit a project's requirements.txt for known vulnerable Python package versions (via pip-audit).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Project path containing requirements.txt (default current directory)"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consult_gemini",
            "description": "Ask Google Gemini (a different AI model) for a second opinion, deeper research, or broader/more thorough information on a question — use when a query needs more investigation than you can give directly.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The question or topic to research"}
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
    "run_shell": run_shell,
    "git_status": git_status,
    "git_diff": git_diff,
    "run_python_snippet": run_python_snippet,
    "run_tests": run_tests,
    "lint_code": lint_code,
    "port_scan": port_scan,
    "dns_lookup": dns_lookup,
    "whois_lookup": whois_lookup,
    "check_ssl_cert": check_ssl_cert,
    "check_security_headers": check_security_headers,
    "check_python_dependencies": check_python_dependencies,
    "consult_gemini": consult_gemini,
}

GREETINGS = {"hey", "hi", "hello", "yo", "sup", "good morning", "good evening", "good afternoon", "morning", "evening"}

MAX_TOOL_ITERATIONS = 8

PROACTIVE_PROMPT_TEMPLATE = """You are JOESTAR, briefly reviewing your own state in the background — the user, {name}, has not spoken to you right now.

Look at today's schedule and the recent conversation below. Decide if there's something worth proactively telling {name} right now:
- A calendar event starting within the next 30 minutes
- A task, plan, or question from the recent conversation that seems worth checking in on

Be conservative — most checks should find nothing worth mentioning. If there's nothing worth surfacing, respond with exactly: NOTHING
Otherwise, write ONE short, natural message addressed to {name}, at most 2 sentences, in your usual voice.

{name} is the verified, currently signed-in identity — the recent conversation below may belong to a different identity from an earlier session; if it names someone else, ignore that name and address this message to {name}."""


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

    def _gemini_fallback(self, user_input: str, groq_error: Exception) -> str:
        """Called when Groq itself fails — answers via Gemini instead, without tool access."""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return self._local_fallback(user_input, groq_error)
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=user_input,
                config=genai_types.GenerateContentConfig(
                    system_instruction=(
                        f"You are JOESTAR, a personal AI assistant, temporarily running on a backup model "
                        f"because your primary model is unavailable. The user's name is {self.user_name}. "
                        f"Respond in plain natural prose — no Markdown syntax — since this may be read aloud."
                    )
                ),
            )
            text = clean_response(response.text or "")
            return text or self._local_fallback(user_input, groq_error)
        except Exception as gemini_error:
            return self._local_fallback(user_input, gemini_error)

    def _local_fallback(self, user_input: str, prior_error: Exception) -> str:
        """Last resort when both cloud models are unreachable — a small model running fully offline, no API key or rate limits."""
        system = (
            f"You are JOESTAR, a personal AI assistant, running fully offline on a small local backup model "
            f"because both your primary and secondary cloud models are unavailable. The user's name is "
            f"{self.user_name}. Respond in plain natural prose — no Markdown syntax."
        )
        text = local_llm_generate(user_input, system=system)
        if text and not text.startswith("Local model unavailable"):
            return clean_response(text)
        return f"All of my models are unreachable right now, {self.user_name}: {prior_error}"

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

        # Simple, tool-free queries (greetings) don't need the bigger model's
        # reasoning depth — the smaller model answers just as well, faster.
        model = "openai/gpt-oss-20b" if is_greeting else "openai/gpt-oss-120b"

        for iteration in range(MAX_TOOL_ITERATIONS):
            kwargs = dict(
                model=model,
                max_tokens=4096,
                messages=messages,
            )

            if use_tools:
                kwargs["tools"] = TOOLS
                kwargs["tool_choice"] = "auto"
                kwargs["parallel_tool_calls"] = True

            try:
                response = await asyncio.to_thread(self.client.chat.completions.create, **kwargs)
            except Exception as e:
                # Groq itself is having issues — fall back to Gemini so the
                # user still gets an answer, even without tool access this turn.
                final = await asyncio.to_thread(self._gemini_fallback, user_input, e)
                await asyncio.to_thread(self.memory.save, user_input, final)
                return final
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