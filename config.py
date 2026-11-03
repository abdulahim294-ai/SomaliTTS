import math
import os
from dataclasses import dataclass


MIN_REQUEST_BODY_BYTES = 512 * 1024
MAX_REQUEST_BODY_BYTES = 10 * 1024 * 1024


def _number(env: dict[str, str], name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(env.get(name, str(default)))
    except (TypeError, ValueError):
        return default
    if not math.isfinite(value):
        return default
    return min(max(value, minimum), maximum)


def _integer(env: dict[str, str], name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(env.get(name, str(default)))
    except (TypeError, ValueError):
        return default
    return min(max(value, minimum), maximum)


def parse_cors_origins(value: str | None = None) -> list[str]:
    raw = value if value is not None else os.getenv(
        "CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    )
    origins = [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]
    if "*" in origins:
        raise ValueError("CORS_ALLOWED_ORIGINS must not contain wildcard origins")
    return list(dict.fromkeys(origins))


@dataclass(frozen=True)
class Settings:
    request_timeout_seconds: float = 300
    health_timeout_seconds: float = 3
    health_cache_seconds: float = 15
    rate_limit_requests: int = 10
    rate_limit_window_seconds: int = 60
    rate_limit_max_clients: int = 4096
    max_concurrent_synthesis: int = 2
    concurrency_wait_seconds: float = 2
    retry_attempts: int = 2
    retry_base_seconds: float = 0.2
    max_request_body_bytes: int = 1_048_576


def load_settings(env: dict[str, str] | None = None) -> Settings:
    source = os.environ if env is None else env
    return Settings(
        request_timeout_seconds=_number(source, "TTS_REQUEST_TIMEOUT_SECONDS", 300, 1, 900),
        health_timeout_seconds=_number(source, "PROVIDER_HEALTH_TIMEOUT_SECONDS", 3, 0.1, 15),
        health_cache_seconds=_number(source, "PROVIDER_HEALTH_CACHE_SECONDS", 15, 1, 300),
        rate_limit_requests=_integer(source, "TTS_RATE_LIMIT_REQUESTS", 10, 1, 10000),
        rate_limit_window_seconds=_integer(source, "TTS_RATE_LIMIT_WINDOW_SECONDS", 60, 1, 3600),
        rate_limit_max_clients=_integer(source, "TTS_RATE_LIMIT_MAX_CLIENTS", 4096, 32, 100000),
        max_concurrent_synthesis=_integer(source, "TTS_MAX_CONCURRENT", 2, 1, 100),
        concurrency_wait_seconds=_number(source, "TTS_CONCURRENCY_WAIT_SECONDS", 2, 0.05, 60),
        retry_attempts=_integer(source, "PROVIDER_RETRY_ATTEMPTS", 2, 1, 3),
        retry_base_seconds=_number(source, "PROVIDER_RETRY_BASE_SECONDS", 0.2, 0.05, 5),
        max_request_body_bytes=_integer(
            source, "MAX_REQUEST_BODY_BYTES", 1_048_576,
            MIN_REQUEST_BODY_BYTES, MAX_REQUEST_BODY_BYTES,
        ),
    )


SETTINGS = load_settings()
