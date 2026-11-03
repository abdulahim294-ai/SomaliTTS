import logging

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import Response

from providers import EdgeTTSProvider, ProviderRegistry

app = FastAPI(title="SomaliTTS")
logger = logging.getLogger(__name__)

MAX_TEXT_LENGTH = 100_000
edge_provider = EdgeTTSProvider()
provider_registry = ProviderRegistry((edge_provider,))
VOICES = {voice.gender: voice.id for voice in edge_provider.voices}


@app.get("/")
def home():
    return {"status": "SomaliTTS running"}


@app.get("/api/v1/health")
def health():
    """Liveness endpoint for platform health checks."""
    return {"status": "ok", "service": "SomaliTTS", "api_version": "v1"}


@app.get("/api/v1/capabilities")
def capabilities():
    """Expose only the provider capabilities that are implemented and tested."""
    return {
        "service": "SomaliTTS",
        "api_version": "v1",
        "providers": [provider.capabilities() for provider in provider_registry.providers],
    }


@app.post("/tts")
async def generate(text: str = Form(...), gender: str = Form("male")):
    if not text.strip():
        raise HTTPException(status_code=422, detail="Text must not be empty")
    if len(text) > MAX_TEXT_LENGTH:
        raise HTTPException(
            status_code=413,
            detail=f"Text must be at most {MAX_TEXT_LENGTH} characters",
        )

    voice_id = VOICES.get(gender.strip().lower())
    if voice_id is None:
        raise HTTPException(status_code=422, detail="Gender must be male or female")

    try:
        audio = await edge_provider.synthesize(text, voice_id)
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
