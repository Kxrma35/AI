from pathlib import Path
from dotenv import load_dotenv

FRONTEND_DIR = Path(__file__).parent
load_dotenv(FRONTEND_DIR / ".env")

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from brain import Brain
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

        await websocket.send_text(json.dumps({
            "type": "text",
            "content": response
        }))

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

# Serve frontend
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)