import httpx

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "qwen2.5:1.5b"


def local_llm_generate(prompt: str, system: str = None) -> str:
    """Generate a response using a local Ollama model — works fully offline, no API key or rate limits."""
    try:
        payload = {"model": MODEL, "prompt": prompt, "stream": False}
        if system:
            payload["system"] = system
        r = httpx.post(OLLAMA_URL, json=payload, timeout=30.0)
        r.raise_for_status()
        return (r.json().get("response") or "").strip()
    except Exception as e:
        return f"Local model unavailable: {e}"
