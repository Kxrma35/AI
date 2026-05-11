import httpx
import base64
import os

FISH_API_KEY = os.getenv("FISH_AUDIO_API_KEY")
FISH_VOICE_ID = os.getenv("FISH_VOICE_ID")  # your cloned/chosen voice

async def synthesize_speech(text: str) -> str:
    """Returns base64-encoded MP3 audio."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.fish.audio/v1/tts",
            headers={
                "Authorization": f"Bearer {FISH_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "text": text,
                "reference_id": FISH_VOICE_ID,
                "format": "mp3",
                "latency": "normal"
            },
            timeout=30.0
        )
        audio_bytes = response.content
        return base64.b64encode(audio_bytes).decode("utf-8")