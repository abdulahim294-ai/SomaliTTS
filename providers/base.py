from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class Voice:
    """A voice available from a provider."""

    id: str
    name: str
    gender: str
    locale: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


class SpeechProvider(ABC):
    """Provider contract for speech synthesis and reporting."""

    provider_id: str
    display_name: str
    voices: tuple[Voice, ...]

    @abstractmethod
    async def synthesize(self, text: str, voice_id: str) -> bytes:
        """Return synthesized audio bytes, or raise on failure."""

    def capabilities(self) -> dict:
        return {
            "id": self.provider_id,
            "name": self.display_name,
            "configured": True,
            "voices": [voice.as_dict() for voice in self.voices],
            "features": {
                "text_to_speech": True,
                "voice_cloning": False,
                "public_voice_sharing": False,
                "durable_long_form_jobs": False,
                "emotional_synthesis": False,
            },
        }


class ProviderRegistry:
    """Map provider IDs to provider implementations."""

    def __init__(self, providers: Iterable[SpeechProvider]):
        self._providers = {provider.provider_id: provider for provider in providers}
        if not self._providers:
            raise ValueError("At least one voice provider must be registered")

    @property
    def providers(self) -> tuple[SpeechProvider, ...]:
        return tuple(self._providers.values())

    def get(self, provider_id: str) -> SpeechProvider:
        try:
            return self._providers[provider_id]
        except KeyError as exc:
            raise LookupError(f"Unknown speech provider: {provider_id}") from exc
