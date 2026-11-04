import asyncio
import logging

import httpx
import pytest
from fastapi.testclient import TestClient

import app as tts_app
import providers.edge as edge_provider_module
from audio_pipeline import AudioProcessingError, AudioProcessingTimeout
from config import Settings, load_settings


# ============================================================
# Fake Edge TTS Provider
# ============================================================

class FakeCommunicate:
    calls = []

    fail = False
    fail_once = False
    fail_connection = False
    partial_fail = False

    gate = None
    entered = None

    # Intentionally fake bytes.
    # API tests must not send these bytes to real FFmpeg.
    audio = b"\xff\xfb\x90\x64fake-mp3-frame"

    def __init__(self, text, voice):
        type(self).calls.append((text, voice))

    async def stream(self):
        if type(self).entered:
            type(self).entered.set()

        if type(self).gate:
            await type(self).gate.wait()

        if type(self).partial_fail:
            type(self).partial_fail = False
            yield {"type": "audio", "data": b"partial"}
            raise ConnectionError("must-not-be-logged")

        if type(self).fail_once:
            type(self).fail_once = False
            raise ConnectionError("transient-secret")

        if type(self).fail_connection:
            raise ConnectionError("transient-secret")

        if type(self).fail:
            raise ValueError("private-provider-exception")

        yield {"type": "audio", "data": type(self).audio}


# ============================================================
# Fake Audio Processing
# ============================================================

async def fake_audio_process(audio: bytes) -> bytes:
    """
    Isolate API tests from the real FFmpeg executable.

    Real FFmpeg behavior is tested independently in
    tests/test_audio_pipeline.py.
    """
    if not isinstance(audio, bytes) or not audio:
        raise AudioProcessingError("Invalid test audio")

    return audio


async def failing_audio_process(audio: bytes) -> bytes:
    raise AudioProcessingError("private-ffmpeg-error")


async def timeout_audio_process(audio: bytes) -> bytes:
    raise AudioProcessingTimeout("private-ffmpeg-timeout")


# ============================================================
# Test Setup
# ============================================================

def setup_function():
    FakeCommunicate.calls = []

    FakeCommunicate.fail = False
    FakeCommunicate.fail_once = False
    FakeCommunicate.fail_connection = False
    FakeCommunicate.partial_fail = False

    FakeCommunicate.gate = None
    FakeCommunicate.entered = None

    FakeCommunicate.audio = b"\xff\xfb\x90\x64fake-mp3-frame"

    # Patch Edge TTS at the provider boundary.
    edge_provider_module.edge_tts.Communicate = FakeCommunicate

    # Prevent invalid fake MP3 data from reaching real FFmpeg.
    tts_app.audio_pipeline.process = fake_audio_process

    # Reset application state.
    tts_app._health_cache.clear()

    tts_app._rate_limiter = tts_app.RateLimiter(
        64,
        1000,
        60,
    )

    tts_app._synthesis_semaphore = asyncio.Semaphore(
        tts_app.MAX_CONCURRENT_SYNTHESIS
    )


# ============================================================
# Configuration Tests
# ============================================================

def test_configuration_malformed_and_bounds():
    config = load_settings({
        "TTS_REQUEST_TIMEOUT_SECONDS": "nonsense",
        "TTS_MAX_CONCURRENT": "9999",
        "PROVIDER_RETRY_ATTEMPTS": "-1",
        "TTS_CONCURRENCY_WAIT_SECONDS": "nan",
    })

    assert config.request_timeout_seconds == 300
    assert config.max_concurrent_synthesis == 100
    assert config.retry_attempts == 1
    assert config.concurrency_wait_seconds == 2

    bounded = load_settings({
        "TTS_REQUEST_TIMEOUT_SECONDS": "0",
        "PROVIDER_HEALTH_TIMEOUT_SECONDS": "999",
    })

    assert bounded.request_timeout_seconds == 1
    assert bounded.health_timeout_seconds == 15


def test_request_body_limit_supports_full_utf8_text_and_clamps_minimum():
    minimum = load_settings({
        "MAX_REQUEST_BODY_BYTES": "1",
    })

    assert minimum.max_request_body_bytes >= 512 * 1024
    assert minimum.max_request_body_bytes >= (
        100_000 * 4 + 16 * 1024
    )

    maximum = load_settings({
        "MAX_REQUEST_BODY_BYTES": "999999999",
    })

    assert maximum.max_request_body_bytes == 10 * 1024 * 1024


# ============================================================
# Rate Limiter Tests
# ============================================================

def test_limiter_expires_entries_and_caps_clients():
    limiter = tts_app.RateLimiter(2, 1, 10)

    assert limiter.check("a", now=1) is None
    assert limiter.check("a", now=2) is not None

    limiter.check("b", now=3)
    limiter.check("c", now=20)

    assert len(limiter.clients) <= 2
    assert "a" not in limiter.clients


def test_rate_limit_and_retry_after():
    tts_app._rate_limiter = tts_app.RateLimiter(
        64,
        1,
        60,
    )

    client = TestClient(tts_app.app)

    first = client.post(
        "/tts",
        data={"text": "one"},
    )

    assert first.status_code == 200

    limited = client.post(
        "/tts",
        data={"text": "two"},
    )

    assert limited.status_code == 429
    assert limited.headers["retry-after"]


# ============================================================
# Health Check Tests
# ============================================================

def test_ready_checks_cache_and_degrade(monkeypatch):
    calls = []

    async def healthy():
        calls.append(1)
        return True

    monkeypatch.setattr(
        tts_app.edge_provider,
        "health_check",
        healthy,
    )

    client = TestClient(tts_app.app)

    assert client.get(
        "/api/v1/health/ready"
    ).status_code == 200

    assert client.get(
        "/api/v1/health/ready"
    ).status_code == 200

    assert len(calls) == 1

    tts_app._health_cache.clear()

    async def timeout():
        await asyncio.sleep(0.1)

    monkeypatch.setattr(
        tts_app,
        "HEALTH_TIMEOUT_SECONDS",
        0.001,
    )

    monkeypatch.setattr(
        tts_app.edge_provider,
        "health_check",
        timeout,
    )

    response = client.get("/api/v1/health/ready")

    assert response.json()["provider"]["status"] == "timeout"


# ============================================================
# CORS Tests
# ============================================================

def test_cors_preflight_allowed_and_rejected():
    client = TestClient(tts_app.app)

    headers = {
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    }

    allowed = client.options(
        "/tts",
        headers=headers,
    )

    assert allowed.status_code == 200

    assert (
        allowed.headers["access-control-allow-origin"]
        == "http://localhost:3000"
    )

    denied = client.options(
        "/tts",
        headers={
            **headers,
            "Origin": "https://bad.example",
        },
    )

    assert denied.status_code == 400

    assert (
        "access-control-allow-origin"
        not in denied.headers
    )


# ============================================================
# Request ID and Validation Tests
# ============================================================

def test_request_ids_and_safe_errors():
    client = TestClient(tts_app.app)

    success = client.get("/api/v1/health")

    assert success.headers["x-request-id"]

    invalid = client.post(
        "/tts",
        data={
            "text": " ",
            "gender": "invalid",
        },
        headers={
            "X-Request-ID": "safe-id.1",
        },
    )

    assert invalid.status_code == 422

    assert invalid.headers["x-request-id"] == "safe-id.1"

    assert invalid.json()["error"] == {
        "code": "invalid_request",
        "message": "Text must not be empty",
        "request_id": "safe-id.1",
    }


# ============================================================
# Security and Logging Tests
# ============================================================

def test_logs_exclude_text_audio_secrets_and_exception(caplog):
    FakeCommunicate.fail = True

    private_text = "UNIQUE_PRIVATE_TEXT"

    with caplog.at_level(
        logging.INFO,
        logger="somalitts",
    ):
        response = TestClient(tts_app.app).post(
            "/tts",
            data={
                "text": private_text,
            },
            headers={
                "Authorization": "Bearer TOP_SECRET",
            },
        )

    assert response.status_code == 502

    for secret in (
        private_text,
        "TOP_SECRET",
        "private-provider-exception",
        FakeCommunicate.audio.decode("latin1"),
    ):
        assert secret not in caplog.text

    assert "provider_error" in caplog.text


def test_body_limit_rejects_oversized_content():
    client = TestClient(tts_app.app)

    response = client.post(
        "/tts",
        content=b"x" * (
            tts_app.SETTINGS.max_request_body_bytes + 1
        ),
        headers={
            "Content-Type": "multipart/form-data; boundary=x",
        },
    )

    assert response.status_code == 413
    assert response.headers.get("x-request-id")


# ============================================================
# FFmpeg API Integration Error Tests
# ============================================================

def test_ffmpeg_processing_failure_returns_safe_502(monkeypatch):
    monkeypatch.setattr(
        tts_app.audio_pipeline,
        "process",
        failing_audio_process,
    )

    response = TestClient(tts_app.app).post(
        "/tts",
        data={
            "text": "Nabad",
            "gender": "male",
        },
    )

    assert response.status_code == 502

    body = response.json()

    assert body["error"]["code"] in (
        "processing_or_provider_error",
        "audio_processing_error",
        "processing_error",
    )

    assert "private-ffmpeg-error" not in response.text


def test_ffmpeg_processing_timeout_returns_safe_504(monkeypatch):
    monkeypatch.setattr(
        tts_app.audio_pipeline,
        "process",
        timeout_audio_process,
    )

    response = TestClient(tts_app.app).post(
        "/tts",
        data={
            "text": "Nabad",
            "gender": "male",
        },
    )

    assert response.status_code == 504

    assert "private-ffmpeg-timeout" not in response.text


# ============================================================
# Concurrent Request Tests
# ============================================================

@pytest.mark.anyio
async def test_real_concurrent_requests_respect_limit_and_wait_503(
    monkeypatch,
):
    monkeypatch.setattr(
        tts_app,
        "CONCURRENCY_WAIT_SECONDS",
        0.05,
    )

    tts_app._synthesis_semaphore = asyncio.Semaphore(1)

    FakeCommunicate.gate = asyncio.Event()

    transport = httpx.ASGITransport(
        app=tts_app.app,
    )

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:

        first = asyncio.create_task(
            client.post(
                "/tts",
                data={"text": "first"},
            )
        )

        await asyncio.sleep(0.02)

        second = await client.post(
            "/tts",
            data={"text": "second"},
        )

        assert second.status_code == 503

        FakeCommunicate.gate.set()

        assert (await first).status_code == 200

        third = await client.post(
            "/tts",
            data={"text": "third"},
        )

        assert third.status_code == 200


@pytest.mark.anyio
async def test_cancellation_releases_slot_and_no_deadlock():
    tts_app._synthesis_semaphore = asyncio.Semaphore(1)

    FakeCommunicate.gate = asyncio.Event()
    FakeCommunicate.entered = asyncio.Event()

    transport = httpx.ASGITransport(
        app=tts_app.app,
    )

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:

        task = asyncio.create_task(
            client.post(
                "/tts",
                data={"text": "cancel"},
            )
        )

        await asyncio.wait_for(
            FakeCommunicate.entered.wait(),
            1,
        )

        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        FakeCommunicate.gate = None

        response = await asyncio.wait_for(
            client.post(
                "/tts",
                data={"text": "after"},
            ),
            1,
        )

        assert response.status_code == 200


# ============================================================
# Provider Retry Tests
# ============================================================

def test_provider_retry_transient_permanent_partial_and_max_attempts(
    monkeypatch,
):
    client = TestClient(tts_app.app)

    FakeCommunicate.fail_once = True

    response = client.post(
        "/tts",
        data={"text": "transient"},
    )

    assert response.status_code == 200
    assert len(FakeCommunicate.calls) == 2

    FakeCommunicate.calls = []
    FakeCommunicate.fail = True

    response = client.post(
        "/tts",
        data={"text": "permanent"},
    )

    assert response.status_code == 502
    assert len(FakeCommunicate.calls) == 1

    FakeCommunicate.calls = []
    FakeCommunicate.fail = False
    FakeCommunicate.partial_fail = True

    response = client.post(
        "/tts",
        data={"text": "partial"},
    )

    assert response.status_code == 502
    assert len(FakeCommunicate.calls) == 1

    FakeCommunicate.calls = []
    FakeCommunicate.fail_connection = True

    monkeypatch.setattr(
        "providers.edge.SETTINGS",
        Settings(
            retry_attempts=3,
            retry_base_seconds=0.05,
            request_timeout_seconds=1,
        ),
    )

    response = client.post(
        "/tts",
        data={"text": "max"},
    )

    assert response.status_code == 502
    assert len(FakeCommunicate.calls) == 3


# ============================================================
# Total Request Deadline Tests
# ============================================================

def test_total_request_deadline(monkeypatch):
    async def slow_stream(self):
        await asyncio.sleep(0.1)

        yield {
            "type": "audio",
            "data": b"audio",
        }

    monkeypatch.setattr(
        FakeCommunicate,
        "stream",
        slow_stream,
    )

    monkeypatch.setattr(
        tts_app,
        "REQUEST_TIMEOUT_SECONDS",
        0.01,
    )

    response = TestClient(tts_app.app).post(
        "/tts",
        data={"text": "slow"},
    )

    assert response.status_code == 504


# ============================================================
# API Contract and Voice Tests
# ============================================================

def test_existing_contract_voices_and_long_chunking():
    client = TestClient(tts_app.app)

    male = client.post(
        "/tts",
        data={
            "text": "Nabad",
            "gender": "male",
        },
    )

    female = client.post(
        "/tts",
        data={
            "text": "Nabad",
            "gender": "female",
        },
    )

    assert male.status_code == 200
    assert female.status_code == 200

    assert male.headers["content-type"] == "audio/mpeg"

    assert male.headers["content-disposition"].endswith(
        'filename="somali_voice.mp3"'
    )

    assert FakeCommunicate.calls[:2] == [
        ("Nabad", "so-SO-MuuseNeural"),
        ("Nabad", "so-SO-UbaxNeural"),
    ]

    FakeCommunicate.calls = []

    text = "Af Soomaali waa luqad qurux badan. " * 100

    response = client.post(
        "/tts",
        data={
            "text": text,
        },
    )

    assert response.status_code == 200

    assert "".join(
        part
        for part, _ in FakeCommunicate.calls
    ) == text


# ============================================================
# Capabilities Tests
# ============================================================

def test_capabilities_reports_audio_processing():
    response = TestClient(tts_app.app).get(
        "/api/v1/capabilities"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["service"] == "SomaliTTS"
    assert data["api_version"] == "v1"

    assert isinstance(data["providers"], list)
    assert len(data["providers"]) >= 1

    audio = data["audio_processing"]

    assert audio["enabled"] is True
    assert audio["engine"] == "FFmpeg"
    assert audio["format"] == "MP3"
    assert audio["sample_rate"] == 48000
    assert audio["channels"] == 1
    assert audio["bitrate"] == "128k"
    assert audio["loudness_normalization"] is True
