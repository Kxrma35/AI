from pathlib import Path
from dotenv import load_dotenv

FRONTEND_DIR = Path(__file__).parent
load_dotenv(FRONTEND_DIR / ".env")

from fastapi import FastAPI, WebSocket
from starlette.websockets import WebSocketDisconnect, WebSocketState
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

PROACTIVE_INTERVAL_SECONDS = 900


def should_speak(text: str) -> bool:
    """Skip TTS for long responses or anything containing code."""
    if len(text) > 600:
        return False
    if "```" in text:
        return False
    return True


async def send_response(websocket: WebSocket, text: str, proactive: bool = False):
    payload = {"type": "text", "content": text}
    if proactive:
        payload["proactive"] = True
    # Send text immediately so UI updates fast
    await websocket.send_text(json.dumps(payload))

    if should_speak(text):
        try:
            audio_b64 = await synthesize_speech(text)
            await websocket.send_text(json.dumps({
                "type": "audio",
                "content": audio_b64
            }))
        except Exception as e:
            print(f"[Voice] TTS error: {e}")


async def proactive_loop(websocket: WebSocket):
    """Periodically check whether JOESTAR should speak up unprompted."""
    while True:
        await asyncio.sleep(PROACTIVE_INTERVAL_SECONDS)
        try:
            message = await brain.proactive_check()
            if message:
                await send_response(websocket, message, proactive=True)
        except Exception as e:
            print(f"[Proactive] error: {e}")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    try:
        briefing = await brain.proactive_check()
        if briefing:
            await send_response(websocket, briefing, proactive=True)
    except Exception as e:
        print(f"[Proactive] briefing error: {e}")

    bg_task = asyncio.create_task(proactive_loop(websocket))

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            user_input = message.get("text", "")

            try:
                response = await brain.think(user_input)
            except Exception as e:
                response = f"Brain error: {e}"

            await send_response(websocket, response)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        bg_task.cancel()


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