from pathlib import Path
from dotenv import load_dotenv

FRONTEND_DIR = Path(__file__).parent
load_dotenv(FRONTEND_DIR / ".env")

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from brain import Brain
from voice import synthesize_speech
from tools.web_search import search_web
import json
import asyncio

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

brain = Brain()


def should_speak(text: str) -> bool:
    """Skip TTS for long responses or anything containing code."""
    if len(text) > 600:
        return False
    if "```" in text:
        return False
    return True


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        message = json.loads(data)
        user_input = message.get("text", "")

        try:
            response = await brain.think(user_input)
        except Exception as e:
            response = f"Brain error: {e}"

        # Send text immediately so UI updates fast
        await websocket.send_text(json.dumps({
            "type": "text",
            "content": response
        }))

        # Only speak short, non-code responses
        if should_speak(response):
            try:
                audio_b64 = await synthesize_speech(response)
                await websocket.send_text(json.dumps({
                    "type": "audio",
                    "content": audio_b64
                }))
            except Exception as e:
                print(f"[Voice] TTS error: {e}")


@app.post("/search")
async def search_endpoint(query: dict):
    search_query = query.get("query", "")
    if not search_query:
        return {"error": "No query provided"}
    try:
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, search_web, search_query)
        return {"query": search_query, "results": results}
    except Exception as e:
        return {"error": str(e)}


@app.get("/health")
def health():
    return {"status": "online"}


@app.get("/test-voice")
async def test_voice():
    try:
        audio_b64 = await synthesize_speech("Online and ready, Sir.")
        return {"status": "ok", "audio_length": len(audio_b64)}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# Serve frontend — must be last
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)