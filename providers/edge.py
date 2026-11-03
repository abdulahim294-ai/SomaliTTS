import asyncio
import random
import time

import edge_tts

from providers.base import SpeechProvider, Voice

CHUNK_SIZE = 2500
SYNTHESIS_TIMEOUT_SECONDS = 60


class EdgeTTSProvider(SpeechProvider):
    """Microsoft Edge TTS adapter with bounded health and synthesis calls."""

    provider_id = "edge-tts"
    display_name = "Microsoft Edge TTS"
    voices = (
        Voice(id="so-SO-MuuseNeural", name="Muuse", gender="male", locale="so-SO"),
        Voice(id="so-SO-UbaxNeural", name="Ubax", gender="female", locale="so-SO"),
    )

    async def health_check(self) -> bool:
        """Check upstream voice-list reachability without synthesizing speech."""
        upstream_voices = await edge_tts.list_voices()
        configured = {voice.id for voice in self.voices}
        available = {item.get("Name") for item in upstream_voices if isinstance(item, dict)}
        return configured.issubset(available)

    async def synthesize(self, text: str, voice_id: str) -> bytes:
        deadline = time.monotonic() + float(__import__("os").getenv("TTS_REQUEST_TIMEOUT_SECONDS", "300"))
        audio_parts: list[bytes] = []
        for chunk in split_text(text):
            chunk_audio = bytearray()
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
                    await asyncio.wait_for(
                        collect_audio(), timeout=min(SYNTHESIS_TIMEOUT_SECONDS, remaining)
                    )
                    chunk_audio = attempt_audio
                    break
                except (ConnectionError, OSError):
                    # Retry only an incomplete current chunk before emitting bytes from it.
                    # A retry cannot replay earlier completed chunks.
                    attempt += 1
                    remaining = deadline - time.monotonic()
                    if attempt >= _retry_attempts() or remaining <= 0 or attempt_audio:
                        raise
                    base = _retry_base_seconds()
                    delay = min(base * (2 ** (attempt - 1)) * random.uniform(0.75, 1.25), remaining)
                    await asyncio.sleep(delay)
                except asyncio.TimeoutError as exc:
                    raise TimeoutError("Speech provider timed out") from exc

            if not chunk_audio:
                raise RuntimeError("Speech provider returned no audio")
            audio_parts.append(bytes(chunk_audio))

        return b"".join(audio_parts)


def _retry_attempts() -> int:
    import os

    try:
        return max(1, min(3, int(os.getenv("PROVIDER_RETRY_ATTEMPTS", "2"))))
    except ValueError:
        return 2


def _retry_base_seconds() -> float:
    import os

    try:
        return max(0.05, float(os.getenv("PROVIDER_RETRY_BASE_SECONDS", "0.2")))
    except ValueError:
        return 0.2


def split_text(text: str, max_length: int = CHUNK_SIZE) -> list[str]:
    """Split long text while preserving word boundaries when possible."""
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
