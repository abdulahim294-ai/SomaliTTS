import asyncio
import random
import time

import edge_tts

from config import SETTINGS
from providers.base import SpeechProvider, Voice

CHUNK_SIZE = 2500
SYNTHESIS_TIMEOUT_SECONDS = 60


class EdgeTTSProvider(SpeechProvider):
    """Microsoft Edge TTS adapter with bounded provider operations."""

    provider_id = "edge-tts"
    display_name = "Microsoft Edge TTS"
    voices = (
        Voice(id="so-SO-MuuseNeural", name="Muuse", gender="male", locale="so-SO"),
        Voice(id="so-SO-UbaxNeural", name="Ubax", gender="female", locale="so-SO"),
    )

    async def health_check(self) -> bool:
        upstream_voices = await edge_tts.list_voices()
        configured = {voice.id for voice in self.voices}
        available = {item.get("Name") for item in upstream_voices if isinstance(item, dict)}
        return configured.issubset(available)

    async def synthesize(self, text: str, voice_id: str) -> bytes:
        deadline = time.monotonic() + SETTINGS.request_timeout_seconds
        audio_parts: list[bytes] = []
        for chunk in split_text(text):
            attempt = 0
            while True:
                communicate = edge_tts.Communicate(chunk, voice_id)
                attempt_audio = bytearray()

                async def collect_audio() -> None:
                    async for event in communicate.stream():
                        if event.get("type") == "audio":
                            attempt_audio.extend(event.get("data", b""))

                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Total speech request deadline exceeded")
                try:
                    await asyncio.wait_for(collect_audio(), timeout=min(SYNTHESIS_TIMEOUT_SECONDS, remaining))
                    if not attempt_audio:
                        raise RuntimeError("Speech provider returned no audio")
                    audio_parts.append(bytes(attempt_audio))
                    break
                except (ConnectionError, OSError):
                    attempt += 1
                    remaining = deadline - time.monotonic()
                    if attempt >= SETTINGS.retry_attempts or remaining <= 0 or attempt_audio:
                        raise
                    delay = SETTINGS.retry_base_seconds * (2 ** (attempt - 1)) * random.uniform(0.75, 1.25)
                    await asyncio.sleep(min(delay, remaining))
                except asyncio.TimeoutError as exc:
                    raise TimeoutError("Speech provider timed out") from exc
        return b"".join(audio_parts)


def split_text(text: str, max_length: int = CHUNK_SIZE) -> list[str]:
    chunks: list[str] = []
    remaining = text
    while len(remaining) > max_length:
        boundary = max_length
        while boundary > 0 and not remaining[boundary - 1].isspace():
            boundary -= 1
        if boundary == 0:
            boundary = max_length
        chunks.append(remaining[:boundary])
        remaining = remaining[boundary:]
    if remaining:
        chunks.append(remaining)
    return chunks
