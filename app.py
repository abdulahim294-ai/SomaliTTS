import asyncio
import logging
from typing import AsyncIterator

import edge_tts
from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import Response

app = FastAPI(title="SomaliTTS")
logger = logging.getLogger(__name__)

VOICES = {
    "male": "so-SO-MuuseNeural",
    "female": "so-SO-UbaxNeural",
}
CHUNK_SIZE = 2500
MAX_TEXT_LENGTH = 100_000
SYNTHESIS_TIMEOUT_SECONDS = 60


def split_text(text: str, max_length: int = CHUNK_SIZE) -> list[str]:
    """Split long text without dropping whitespace or splitting words unnecessarily."""
    chunks = []
    remaining = text
    while len(remaining) > max_length:
        boundary = max_length
        while boundary > 0 and not remaining[boundary - 1].isspace():
            boundary -= 1
        if boundary == 0:  # A single unbroken token is longer than the limit.
            boundary = max_length
        chunks.append(remaining[:boundary])
        remaining = remaining[boundary:]
    if remaining:
        chunks.append(remaining)
    return chunks


async def synthesize(text: str, voice: str) -> bytes:
    """Synthesize text in bounded requests and combine the MP3 stream segments."""
    audio_parts: list[bytes] = []
    for chunk in split_text(text):
        communicate = edge_tts.Communicate(chunk, voice)
        chunk_audio = bytearray()

        async def collect_audio() -> None:
            async for event in communicate.stream():
                if event.get("type") == "audio":
                    chunk_audio.extend(event.get("data", b""))

        try:
            await asyncio.wait_for(
                collect_audio(), timeout=SYNTHESIS_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError as exc:
            raise TimeoutError("Speech provider timed out") from exc

        if not chunk_audio:
            raise RuntimeError("Speech provider returned no audio")
        audio_parts.append(bytes(chunk_audio))

    return b"".join(audio_parts)


@app.get("/")
def home():
    return {"status": "SomaliTTS running"}


@app.post("/tts")
async def generate(text: str = Form(...), gender: str = Form("male")):
    if not text.strip():
        raise HTTPException(status_code=422, detail="Text must not be empty")
    if len(text) > MAX_TEXT_LENGTH:
        raise HTTPException(
            status_code=413,
            detail=f"Text must be at most {MAX_TEXT_LENGTH} characters",
        )

    voice = VOICES.get(gender.strip().lower())
    if voice is None:
        raise HTTPException(status_code=422, detail="Gender must be male or female")

    try:
        audio = await synthesize(text, voice)
    except TimeoutError:
        logger.warning("Edge TTS timed out while synthesizing speech")
        raise HTTPException(status_code=504, detail="Speech generation timed out")
    except Exception:
        logger.exception("Edge TTS synthesis failed")
        raise HTTPException(
            status_code=502,
            detail="Speech provider failed to generate audio; please try again",
        )

    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={"Content-Disposition": 'attachment; filename="somali_voice.mp3"'},
    )
