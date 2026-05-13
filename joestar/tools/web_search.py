import httpx
import os

def search_web(query: str) -> list:
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        raise RuntimeError("SERPER_API_KEY not set in .env")
    response = httpx.post(
        "https://google.serper.dev/search",
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        json={"q": query, "num": 5},
        timeout=15.0,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Serper {response.status_code}: {response.text[:200]}")
    results = response.json().get("organic", [])
    return [{"title": r.get("title", ""), "snippet": r.get("snippet", ""), "link": r.get("link", "")} for r in results]