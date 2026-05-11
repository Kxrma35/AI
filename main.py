from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from brain import Brain
from voice import synthesize_speech
import json

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

        # Stream response from brain
        response = await brain.think(user_input)

        # Send text back
        await websocket.send_text(json.dumps({
            "type": "text",
            "content": response
        }))

        # Synthesize and send audio
        audio_b64 = await synthesize_speech(response)
        await websocket.send_text(json.dumps({
            "type": "audio",
            "content": audio_b64
        }))

@app.get("/health")
def health():
    return {"status": "online"}

# Serve frontend
app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")