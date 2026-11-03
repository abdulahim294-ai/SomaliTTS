import asyncio

import edge_tts

from providers.base import SpeechProvider, Voice

CHUNK_SIZE = 2500
SYNTHESIS_TIMEOUT_SECONDS = 60


class EdgeTTSProvider(SpeechProvider):
    """Microsoft Edge TTS provider used by SomaliTTS."""

    provider_id = "edge-tts"
    display_name = "Microsoft Edge TTS"
    voices = (
        Voice(
            id="so-SO-MuuseNeural",
            name="Muuse",
            gender="male",
            locale="so-SO",
        ),
        Voice(
            id="so-SO-UbaxNeural",
            name="Ubax",
            gender="female",
            locale="so-SO",
        ),
    )

    async def synthesize(self, text: str, voice_id: str) -> bytes:
        audio_parts: list[bytes] = []
        for chunk in split_text(text):
            communicate = edge_tts.Communicate(chunk, voice_id)
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
