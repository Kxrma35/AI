import os

from google import genai
from google.genai import types

MODEL = "gemini-3.6-flash"

NO_MARKDOWN_INSTRUCTION = (
    "Respond in plain natural prose only — no Markdown syntax (no **bold**, "
    "no bullet/numbered lists, no tables, no headings). Your answer will be "
    "relayed as-is by another assistant, including read aloud via voice."
)


def consult_gemini(query: str) -> str:
    """Ask Google Gemini for a second opinion or deeper research on a query."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "Gemini is not configured (GEMINI_API_KEY not set)."
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=MODEL,
            contents=query,
            config=types.GenerateContentConfig(system_instruction=NO_MARKDOWN_INSTRUCTION),
        )
        return response.text or "Gemini returned no content."
    except Exception as e:
        return f"Gemini consult failed: {e}"
