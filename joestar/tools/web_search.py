import httpx
import os

def search_web(query: str) -> list:
    api_key = os.getenv("SERPER_API_KEY")
    response = httpx.post(
        "https://google.serper.dev/search",
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        json={"q": query, "num": 5}
    )
    results = response.json().get("organic", [])
    return [{"title": r["title"], "snippet": r["snippet"], "link": r["link"]} for r in results]