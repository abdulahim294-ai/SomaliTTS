import asyncio
import json
import logging
import os
import re
import secrets
import time
from collections import defaultdict, deque
from email.utils import formatdate
from typing import Deque

import edge_tts
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from providers import EdgeTTSProvider, ProviderRegistry


def _int_setting(name: str, default: int, minimum: int = 1) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, value)


def _float_setting(name: str, default: float, minimum: float = 0.05) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, value)


def parse_cors_origins(value: str | None = None) -> list[str]:
    raw = value if value is not None else os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )
    origins = [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]
    if "*" in origins:
        raise ValueError("CORS_ALLOWED_ORIGINS must not contain wildcard origins")
    return list(dict.fromkeys(origins))


MAX_TEXT_LENGTH = 100_000
REQUEST_TIMEOUT_SECONDS = _float_setting("TTS_REQUEST_TIMEOUT_SECONDS", 300)
HEALTH_TIMEOUT_SECONDS = _float_setting("PROVIDER_HEALTH_TIMEOUT_SECONDS", 3)
HEALTH_CACHE_SECONDS = _float_setting("PROVIDER_HEALTH_CACHE_SECONDS", 15)
RATE_LIMIT_REQUESTS = _int_setting("TTS_RATE_LIMIT_REQUESTS", 10)
RATE_LIMIT_WINDOW_SECONDS = _int_setting("TTS_RATE_LIMIT_WINDOW_SECONDS", 60)
MAX_CONCURRENT_SYNTHESIS = _int_setting("TTS_MAX_CONCURRENT", 2)
CONCURRENCY_WAIT_SECONDS = _float_setting("TTS_CONCURRENCY_WAIT_SECONDS", 2)
RETRY_ATTEMPTS = min(_int_setting("PROVIDER_RETRY_ATTEMPTS", 2), 3)
RETRY_BASE_SECONDS = _float_setting("PROVIDER_RETRY_BASE_SECONDS", 0.2)

app = FastAPI(title="SomaliTTS")
logger = logging.getLogger("somalitts")
edge_provider = EdgeTTSProvider()
provider_registry = ProviderRegistry((edge_provider,))
VOICES = {voice.gender: voice.id for voice in edge_provider.voices}

app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID", "Retry-After"],
)

_request_id_pattern = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_synthesis_semaphore = asyncio.Semaphore(MAX_CONCURRENT_SYNTHESIS)
_rate_events: dict[str, Deque[float]] = defaultdict(deque)
_health_cache: dict[str, tuple[float, bool, str]] = {}


@app.middleware("http")
async def request_context(request: Request, call_next):
    incoming_id = request.headers.get("X-Request-ID", "")
    request_id = incoming_id if _request_id_pattern.fullmatch(incoming_id) else secrets.token_hex(16)
    request.state.request_id = request_id
    started = time.monotonic()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        log_entry = {
            "event": "http_request",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": status_code,
            "duration_ms": round((time.monotonic() - started) * 1000, 2),
        }
        logger.info(json.dumps(log_entry, separators=(",", ":")))


@app.exception_handler(HTTPException)
async def safe_http_error(request: Request, exc: HTTPException):
    status = exc.status_code
    known_messages = {
        413: str(exc.detail),
        422: str(exc.detail) if isinstance(exc.detail, str) else "Invalid request",
        429: "Rate limit exceeded; retry after the indicated interval",
        503: "Speech service is temporarily at capacity",
        504: "Speech generation timed out",
        502: "Speech provider failed to generate audio; please try again",
    }
    code = {
        413: "text_too_large",
        422: "invalid_request",
        429: "rate_limit_exceeded",
        503: "capacity_exhausted",
        504: "provider_timeout",
        502: "provider_error",
    }.get(status, "request_failed")
    message = known_messages.get(status, "Request could not be completed")
    body = {
        "detail": message,
        "error": {"code": code, "message": message, "request_id": getattr(request.state, "request_id", None)},
    }
    return JSONResponse(status_code=status, content=body, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def safe_validation_error(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", None)
    message = "Request validation failed"
    return JSONResponse(
        status_code=422,
        content={
            "detail": message,
            "error": {"code": "invalid_request", "message": message, "request_id": request_id},
        },
    )


def _client_key(request: Request) -> str:
    # Deliberately use the socket peer only. Forwarding headers are untrusted unless
    # a deployment explicitly adds a trusted-proxy implementation in a later change.
    return request.client.host if request.client else "unknown"


def _check_rate_limit(client_key: str, now: float | None = None) -> float | None:
    current = time.monotonic() if now is None else now
    events = _rate_events[client_key]
    cutoff = current - RATE_LIMIT_WINDOW_SECONDS
    while events and events[0] <= cutoff:
        events.popleft()
    if len(events) >= RATE_LIMIT_REQUESTS:
        return max(1.0, events[0] + RATE_LIMIT_WINDOW_SECONDS - current)
    events.append(current)
    return None


@app.get("/")
def home():
    return {"status": "SomaliTTS running"}


@app.get("/api/v1/health")
def health():
    """Lightweight liveness probe; no upstream provider request is made."""
    return {"status": "ok", "service": "SomaliTTS", "api_version": "v1"}


async def _cached_provider_health(provider: EdgeTTSProvider) -> tuple[bool, str]:
    now = time.monotonic()
    cached = _health_cache.get(provider.provider_id)
    if cached and now - cached[0] < HEALTH_CACHE_SECONDS:
        return cached[1], cached[2]
    try:
        reachable = await asyncio.wait_for(
            provider.health_check(), timeout=HEALTH_TIMEOUT_SECONDS
        )
        result = (bool(reachable), "reachable" if reachable else "unreachable")
    except asyncio.TimeoutError:
        result = (False, "timeout")
    except Exception:
        result = (False, "unreachable")
    _health_cache[provider.provider_id] = (time.monotonic(), result[0], result[1])
    return result


@app.get("/api/v1/health/ready")
async def readiness(request: Request):
    reachable, provider_status = await _cached_provider_health(edge_provider)
    status = "ready" if reachable else "degraded"
    body = {
        "status": status,
        "application": "alive",
        "provider": {
            "id": edge_provider.provider_id,
            "configured": True,
            "reachable": reachable,
            "status": provider_status,
        },
        "request_id": request.state.request_id,
    }
    return JSONResponse(status_code=200 if reachable else 503, content=body)


@app.get("/api/v1/capabilities")
def capabilities():
    return {
        "service": "SomaliTTS",
        "api_version": "v1",
        "providers": [provider.capabilities() for provider in provider_registry.providers],
    }


@app.post("/tts")
async def generate(text: str = Form(...), gender: str = Form("male"), request: Request = None):
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

    retry_after = _check_rate_limit(_client_key(request)) if request else None
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(max(1, int(retry_after + 0.999)))} ,
        )

    acquired = False
    try:
        try:
            await asyncio.wait_for(
                _synthesis_semaphore.acquire(), timeout=CONCURRENCY_WAIT_SECONDS
            )
            acquired = True
        except asyncio.TimeoutError as exc:
            raise HTTPException(
                status_code=503,
                detail="Speech service is temporarily at capacity",
                headers={"Retry-After": "2"},
            ) from exc
        try:
            audio = await asyncio.wait_for(
                edge_provider.synthesize(text, voice_id), timeout=REQUEST_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError as exc:
            raise TimeoutError("Total speech request deadline exceeded") from exc
    except HTTPException:
        raise
    except TimeoutError:
        logger.warning(json.dumps({
            "event": "provider_failure",
            "provider": edge_provider.provider_id,
            "category": "timeout",
            "request_id": getattr(request.state, "request_id", None) if request else None,
        }, separators=(",", ":")))
        raise HTTPException(status_code=504, detail="Speech generation timed out")
    except Exception as exc:
        category = "connection" if isinstance(exc, (ConnectionError, OSError)) else "provider_error"
        logger.warning(json.dumps({
            "event": "provider_failure",
            "provider": edge_provider.provider_id,
            "category": category,
            "request_id": getattr(request.state, "request_id", None) if request else None,
        }, separators=(",", ":")))
        raise HTTPException(
            status_code=502,
            detail="Speech provider failed to generate audio; please try again",
        )
    finally:
        if acquired:
            _synthesis_semaphore.release()

    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={"Content-Disposition": 'attachment; filename="somali_voice.mp3"'},
    )
