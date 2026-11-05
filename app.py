import asyncio
import json
import logging
import re
import secrets
import time
from collections import OrderedDict, deque
from typing import Deque

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from config import SETTINGS, parse_cors_origins
from audio_pipeline import (
    AudioPipeline,
    AudioProcessingError,
    AudioProcessingTimeout,
)
from providers import EdgeTTSProvider, ProviderRegistry
from web_middleware import RequestBodyLimitMiddleware


# ============================================================
# CONFIGURATION
# ============================================================

MAX_TEXT_LENGTH = 100_000

REQUEST_TIMEOUT_SECONDS = SETTINGS.request_timeout_seconds
HEALTH_TIMEOUT_SECONDS = SETTINGS.health_timeout_seconds
HEALTH_CACHE_SECONDS = SETTINGS.health_cache_seconds

RATE_LIMIT_REQUESTS = SETTINGS.rate_limit_requests
RATE_LIMIT_WINDOW_SECONDS = SETTINGS.rate_limit_window_seconds

MAX_CONCURRENT_SYNTHESIS = SETTINGS.max_concurrent_synthesis
CONCURRENCY_WAIT_SECONDS = SETTINGS.concurrency_wait_seconds


# ============================================================
# APPLICATION
# ============================================================

app = FastAPI(
    title="SomaliTTS",
    description="Professional Somali Text-to-Speech API",
    version="1.0.0",
)

logger = logging.getLogger("somalitts")

edge_provider = EdgeTTSProvider()
provider_registry = ProviderRegistry((edge_provider,))

audio_pipeline = AudioPipeline()

VOICES = {
    voice.gender: voice.id
    for voice in edge_provider.voices
}


# ============================================================
# MIDDLEWARE
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID", "Retry-After"],
)

app.add_middleware(
    RequestBodyLimitMiddleware,
    max_bytes=SETTINGS.max_request_body_bytes,
)

_request_id_pattern = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

_synthesis_semaphore = asyncio.Semaphore(
    MAX_CONCURRENT_SYNTHESIS
)

_health_cache: dict[str, tuple[float, bool, str]] = {}


# ============================================================
# RATE LIMITER
# ============================================================

class RateLimiter:
    """Bounded process-local fixed-window rate limiter."""

    def __init__(
        self,
        max_clients: int,
        max_requests: int,
        window_seconds: int,
    ):
        self.max_clients = max_clients
        self.max_requests = max_requests
        self.window_seconds = window_seconds

        self.clients: OrderedDict[str, Deque[float]] = OrderedDict()
        self._last_prune = 0.0

    def check(
        self,
        client_key: str,
        now: float | None = None,
    ) -> float | None:

        current = time.monotonic() if now is None else now
        cutoff = current - self.window_seconds

        if (
            current - self._last_prune >= min(self.window_seconds, 30)
            or len(self.clients) >= self.max_clients
        ):
            for key, events in tuple(self.clients.items()):
                while events and events[0] <= cutoff:
                    events.popleft()

                if not events:
                    self.clients.pop(key, None)

            self._last_prune = current

        events = self.clients.get(client_key)

        if events is None:
            if len(self.clients) >= self.max_clients:
                self.clients.popitem(last=False)

            events = deque()
            self.clients[client_key] = events
        else:
            self.clients.move_to_end(client_key)

        while events and events[0] <= cutoff:
            events.popleft()

        if len(events) >= self.max_requests:
            return max(
                1.0,
                events[0] + self.window_seconds - current,
            )

        events.append(current)
        return None


_rate_limiter = RateLimiter(
    SETTINGS.rate_limit_max_clients,
    RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW_SECONDS,
)


# ============================================================
# REQUEST CONTEXT AND LOGGING
# ============================================================

@app.middleware("http")
async def request_context(request: Request, call_next):

    incoming_id = request.headers.get("X-Request-ID", "")

    request_id = (
        incoming_id
        if _request_id_pattern.fullmatch(incoming_id)
        else secrets.token_hex(16)
    )

    request.state.request_id = request_id

    started = time.monotonic()
    status_code = 500

    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response

    finally:
        logger.info(
            json.dumps(
                {
                    "event": "http_request",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": status_code,
                    "duration_ms": round(
                        (time.monotonic() - started) * 1000,
                        2,
                    ),
                },
                separators=(",", ":"),
            )
        )


# ============================================================
# SAFE ERROR HANDLING
# ============================================================

@app.exception_handler(HTTPException)
async def safe_http_error(
    request: Request,
    exc: HTTPException,
):

    status = exc.status_code

    messages = {
        413: "Request body or text exceeds the configured limit",
        422: (
            str(exc.detail)
            if isinstance(exc.detail, str)
            else "Invalid request"
        ),
        429: "Rate limit exceeded; retry after the indicated interval",
        502: "Speech provider or audio processing failed",
        503: "Speech service is temporarily at capacity",
        504: "Speech generation or audio processing timed out",
    }

    codes = {
        413: "request_too_large",
        422: "invalid_request",
        429: "rate_limit_exceeded",
        502: "processing_or_provider_error",
        503: "capacity_exhausted",
        504: "processing_timeout",
    }

    message = messages.get(
        status,
        "Request could not be completed",
    )

    return JSONResponse(
        status_code=status,
        content={
            "detail": message,
            "error": {
                "code": codes.get(status, "request_failed"),
                "message": message,
                "request_id": getattr(
                    request.state,
                    "request_id",
                    None,
                ),
            },
        },
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def safe_validation_error(
    request: Request,
    exc: RequestValidationError,
):

    message = "Request validation failed"

    return JSONResponse(
        status_code=422,
        content={
            "detail": message,
            "error": {
                "code": "invalid_request",
                "message": message,
                "request_id": getattr(
                    request.state,
                    "request_id",
                    None,
                ),
            },
        },
    )


# ============================================================
# CLIENT IDENTIFICATION
# ============================================================

def _client_key(request: Request) -> str:

    # Forwarding headers are untrusted.
    # Only the direct socket peer is used.

    return (
        request.client.host
        if request.client
        else "unknown"
    )


# ============================================================
# HEALTH ENDPOINTS
# ============================================================

@app.get("/")
def home():

    return {
        "status": "SomaliTTS running",
        "service": "SomaliTTS",
    }


@app.api_route("/api/v1/health", methods=["GET", "HEAD"])
def health():

    return {
        "status": "ok",
        "service": "SomaliTTS",
        "api_version": "v1",
    }


async def _cached_provider_health(
    provider: EdgeTTSProvider,
) -> tuple[bool, str]:

    now = time.monotonic()

    cached = _health_cache.get(provider.provider_id)

    if cached and now - cached[0] < HEALTH_CACHE_SECONDS:
        return cached[1], cached[2]

    try:
        reachable = await asyncio.wait_for(
            provider.health_check(),
            timeout=HEALTH_TIMEOUT_SECONDS,
        )

        result = (
            bool(reachable),
            "reachable" if reachable else "unreachable",
        )

    except asyncio.TimeoutError:
        result = (False, "timeout")

    except Exception:
        result = (False, "unreachable")

    _health_cache[provider.provider_id] = (
        time.monotonic(),
        result[0],
        result[1],
    )

    return result


@app.get("/api/v1/health/ready")
async def readiness(request: Request):

    reachable, provider_status = await _cached_provider_health(
        edge_provider
    )

    body = {
        "status": "ready" if reachable else "degraded",
        "application": "alive",
        "provider": {
            "id": edge_provider.provider_id,
            "configured": True,
            "reachable": reachable,
            "status": provider_status,
        },
        "request_id": request.state.request_id,
    }

    return JSONResponse(
        status_code=200 if reachable else 503,
        content=body,
    )


# ============================================================
# CAPABILITIES
# ============================================================

@app.get("/api/v1/capabilities")
def capabilities():

    return {
        "service": "SomaliTTS",
        "api_version": "v1",
        "providers": [
            provider.capabilities()
            for provider in provider_registry.providers
        ],
        "audio_processing": {
            "enabled": True,
            "engine": "FFmpeg",
            "format": "MP3",
            "sample_rate": 48000,
            "channels": 1,
            "bitrate": "128k",
            "loudness_normalization": True,
        },
    }


# ============================================================
# TEXT TO SPEECH
# ============================================================

@app.post("/tts")
async def generate(
    request: Request,
    text: str = Form(...),
    gender: str = Form("male"),
):

    # --------------------------------------------------------
    # INPUT VALIDATION
    # --------------------------------------------------------

    if not text.strip():
        raise HTTPException(
            status_code=422,
            detail="Text must not be empty",
        )

    if len(text) > MAX_TEXT_LENGTH:
        raise HTTPException(
            status_code=413,
            detail="Text must not exceed 100,000 characters",
        )

    voice_id = VOICES.get(
        gender.strip().lower()
    )

    if voice_id is None:
        raise HTTPException(
            status_code=422,
            detail="Gender must be male or female",
        )

    # --------------------------------------------------------
    # RATE LIMITING
    # --------------------------------------------------------

    retry_after = _rate_limiter.check(
        _client_key(request)
    )

    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={
                "Retry-After": str(
                    max(1, int(retry_after + 0.999))
                )
            },
        )

    # --------------------------------------------------------
    # SYNTHESIS AND AUDIO PROCESSING
    # --------------------------------------------------------

    acquired = False

    try:

        # Acquire a slot for the complete audio operation.

        try:
            await asyncio.wait_for(
                _synthesis_semaphore.acquire(),
                timeout=CONCURRENCY_WAIT_SECONDS,
            )

            acquired = True

        except asyncio.TimeoutError as exc:
            raise HTTPException(
                status_code=503,
                detail="Speech service is temporarily at capacity",
                headers={"Retry-After": "2"},
            ) from exc

        # Step 1: Generate speech.

        audio = await asyncio.wait_for(
            edge_provider.synthesize(
                text,
                voice_id,
            ),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

        if not audio:
            raise HTTPException(
                status_code=502,
                detail="Speech provider returned empty audio",
            )

        # Step 2: Normalize and encode audio through FFmpeg.

        audio = await audio_pipeline.process(audio)

        if not audio:
            raise AudioProcessingError(
                "Audio pipeline returned empty audio"
            )

    except HTTPException:
        raise

    except asyncio.CancelledError:
        raise

    # --------------------------------------------------------
    # FFMPEG TIMEOUT
    # --------------------------------------------------------

    except AudioProcessingTimeout:
        logger.warning(
            json.dumps(
                {
                    "event": "audio_processing_failure",
                    "category": "timeout",
                    "request_id": request.state.request_id,
                }
            )
        )

        raise HTTPException(
            status_code=504,
            detail="Audio processing timed out",
        )

    # --------------------------------------------------------
    # FFMPEG FAILURE
    # --------------------------------------------------------

    except AudioProcessingError:
        logger.exception(
            json.dumps(
                {
                    "event": "audio_processing_failure",
                    "category": "processing_error",
                    "request_id": request.state.request_id,
                }
            )
        )

        raise HTTPException(
            status_code=502,
            detail="Generated audio could not be processed",
        )

    # --------------------------------------------------------
    # PROVIDER TIMEOUT
    # --------------------------------------------------------

    except (TimeoutError, asyncio.TimeoutError):
        logger.warning(
            json.dumps(
                {
                    "event": "provider_failure",
                    "provider": edge_provider.provider_id,
                    "category": "timeout",
                    "request_id": request.state.request_id,
                }
            )
        )

        raise HTTPException(
            status_code=504,
            detail="Speech generation timed out",
        )

    # --------------------------------------------------------
    # PROVIDER FAILURE
    # --------------------------------------------------------

    except Exception as exc:

        category = (
            "connection"
            if isinstance(exc, (ConnectionError, OSError))
            else "provider_error"
        )

        logger.warning(
            json.dumps(
                {
                    "event": "provider_failure",
                    "provider": edge_provider.provider_id,
                    "category": category,
                    "request_id": request.state.request_id,
                }
            )
        )

        raise HTTPException(
            status_code=502,
            detail="Speech provider failed to generate audio",
        )

    finally:

        if acquired:
            _synthesis_semaphore.release()

    # --------------------------------------------------------
    # AUDIO RESPONSE
    # --------------------------------------------------------

    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": (
                'attachment; filename="somali_voice.mp3"'
            )
        },
    )
