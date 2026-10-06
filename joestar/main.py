from pathlib import Path
from dotenv import load_dotenv

FRONTEND_DIR = Path(__file__).parent
load_dotenv(FRONTEND_DIR / ".env")

from fastapi import FastAPI, HTTPException, Request, WebSocket
from starlette.websockets import WebSocketDisconnect, WebSocketState
from fastapi.staticfiles import StaticFiles
from google.auth.transport import requests as google_auth_requests
from google.oauth2 import id_token as google_id_token
from brain import Brain
from memory import current_user_id
from voice import synthesize_speech
from tools.web_search import search_web
import json
import asyncio
import os

app = FastAPI()

FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID")
_google_auth_request = google_auth_requests.Request()


def verify_firebase_token(token: str) -> dict | None:
    """Verify a Firebase ID token and return its claims, or None if invalid."""
    if not token or not FIREBASE_PROJECT_ID:
        return None
    try:
        return google_id_token.verify_firebase_token(
            token, _google_auth_request, audience=FIREBASE_PROJECT_ID
        )
    except Exception:
        return None


# Optional allow-list: comma-separated emails permitted to use JOESTAR (e.g. "me@example.com").
# JOESTAR can run shell commands and read files on the host, so if sign-up is open to the
# public you should set this. Unset = any signed-in Firebase user is allowed (previous behaviour).
ALLOWED_EMAILS = {e.strip().lower() for e in os.getenv("ALLOWED_EMAILS", "").split(",") if e.strip()}


def authenticate(token: str | None) -> dict | None:
    """Verify the token and the optional email allow-list. Returns claims or None."""
    claims = verify_firebase_token(token)
    if not claims:
        return None
    if ALLOWED_EMAILS and (claims.get("email") or "").lower() not in ALLOWED_EMAILS:
        return None
    return claims


def bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    return header[7:].strip() if header.lower().startswith("bearer ") else None


def uid_of(claims: dict) -> str | None:
    return claims.get("user_id") or claims.get("sub")


# No CORS middleware: the frontend is served from this same origin, so cross-origin
# access (previously allow_origins=["*"]) is neither needed nor wanted.

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-Frame-Options", "DENY")
    # Microphone is used by in-page speech recognition; everything else is off.
    response.headers.setdefault("Permissions-Policy", "microphone=(self), camera=(), geolocation=(), payment=()")
    return response

brain = Brain()

PROACTIVE_INTERVAL_SECONDS = 900
REFLECTION_CHECK_INTERVAL_SECONDS = 3600  # checked hourly; Brain.reflect() itself gates to ~once/day


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


async def reflection_loop(websocket: WebSocket):
    """Periodically check whether a broader look at history surfaces a pattern-based idea."""
    while True:
        await asyncio.sleep(REFLECTION_CHECK_INTERVAL_SECONDS)
        try:
            message = await brain.reflect()
            if message:
                await send_response(websocket, message, proactive=True)
        except Exception as e:
            print(f"[Reflection] error: {e}")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str | None = None):
    await websocket.accept()

    claims = await asyncio.to_thread(authenticate, token)
    if not claims:
        await websocket.send_text(json.dumps({
            "type": "auth_error",
            "content": "Please sign in again, or this account may not be authorised."
        }))
        await websocket.close(code=1008)
        return

    # Scope all memory reads/writes in this connection (and the tasks it spawns) to this user.
    current_user_id.set(uid_of(claims))

    user_name = claims.get("name") or claims.get("email") or "Sir"
    brain.set_user(user_name)

    try:
        briefing = await brain.proactive_check()
        if briefing:
            await send_response(websocket, briefing, proactive=True)
    except Exception as e:
        print(f"[Proactive] briefing error: {e}")

    try:
        idea = await brain.reflect()
        if idea:
            await send_response(websocket, idea, proactive=True)
    except Exception as e:
        print(f"[Reflection] on-connect error: {e}")

    bg_task = asyncio.create_task(proactive_loop(websocket))
    reflection_task = asyncio.create_task(reflection_loop(websocket))

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
        reflection_task.cancel()


@app.post("/search")
async def search_endpoint(request: Request, query: dict):
    if not await asyncio.to_thread(authenticate, bearer_token(request)):
        raise HTTPException(status_code=401, detail="Unauthorized")
    search_query = query.get("query", "")
    if not search_query:
        return {"error": "No query provided"}
    try:
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, search_web, search_query)
        return {"query": search_query, "results": results}
    except Exception as e:
        return {"error": str(e)}


@app.get("/history")
async def get_history(request: Request, limit: int = 50, offset: int = 0):
    claims = await asyncio.to_thread(authenticate, bearer_token(request))
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    current_user_id.set(uid_of(claims))

    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    try:
        items = await asyncio.to_thread(brain.memory.get_history, limit, offset)
        total = await asyncio.to_thread(brain.memory.get_history_count)
        return {"items": items, "total": total, "limit": limit, "offset": offset}
    except Exception as e:
        return {"error": str(e)}


@app.delete("/account/data")
async def delete_my_data(request: Request):
    """Data-deletion request: erase all stored conversations belonging to the signed-in user."""
    claims = await asyncio.to_thread(authenticate, bearer_token(request))
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")
    current_user_id.set(uid_of(claims))
    try:
        deleted = await asyncio.to_thread(brain.memory.delete_user_data)
    except Exception:
        raise HTTPException(status_code=503, detail="Could not reach the database. Nothing was deleted; please try again.")
    return {"status": "deleted", "conversations_deleted": deleted}


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


# Serve frontend — must be last.
# Only an explicit allow-list is public. FRONTEND_DIR also contains .env, *.py, data/ and
# the venv, which must never be downloadable (a plain StaticFiles(directory=FRONTEND_DIR)
# served all of them).
PUBLIC_FILES = {
    "index.html", "login.html", "privacy.html", "terms.html", "refund.html",
    "cookies.html", "licenses.html", "style.css", "legal.css", "legal.js",
    "legal-config.js", "consent.js", "script.js", "login.js", "firebase-config.js",
    "orb-render.js",
}
PUBLIC_PREFIXES = ("vendor/",)


class PublicStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        norm = path.strip("/")
        if norm not in ("", ".") and norm not in PUBLIC_FILES and not norm.startswith(PUBLIC_PREFIXES):
            raise HTTPException(status_code=404)
        return await super().get_response(path, scope)


app.mount("/", PublicStaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)