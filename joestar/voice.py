import edge_tts
import base64
import io
import asyncio

VOICE = "en-GB-RyanNeural"

async def synthesize_speech(text: str) -> str:
    """Returns base64-encoded MP3 audio using Edge TTS."""
    communicate = edge_tts.Communicate(text, VOICE)
    
    audio_bytes = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_bytes += chunk["data"]
    
    return base64.b64encode(audio_bytes).decode("utf-8")