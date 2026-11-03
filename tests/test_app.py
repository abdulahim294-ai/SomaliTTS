import asyncio
import json
import logging
import time

import pytest
from fastapi.testclient import TestClient

import app as tts_app


class FakeCommunicate:
    calls = []
    audio = b"\xff\xfb\x90\x64fake-mp3-frame"
    fail = False
    fail_once = False

    def __init__(self, text, voice):
        self.calls.append((text, voice))

    async def stream(self):
        if self.fail_once:
            type(self).fail_once = False
            raise ConnectionError("mock transient")
        if self.fail:
            raise ValueError("mock permanent provider failure")
        yield {"type": "audio", "data": self.audio}


def setup_function():
    FakeCommunicate.calls = []
    FakeCommunicate.fail = False
    FakeCommunicate.fail_once = False
    FakeCommunicate.audio = b"\xff\xfb\x90\x64fake-mp3-frame"
    tts_app.edge_tts.Communicate = FakeCommunicate
    tts_app._health_cache.clear()
    tts_app._rate_events.clear()
    tts_app._synthesis_semaphore = asyncio.Semaphore(tts_app.MAX_CONCURRENT_SYNTHESIS)


def test_health_endpoint_is_liveness_only():
    response = TestClient(tts_app.app).get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert FakeCommunicate.calls == []


def test_readiness_provider_reachable_and_cached(monkeypatch):
    calls = []

    async def healthy():
        calls.append(1)
        return True

    monkeypatch.setattr(tts_app.edge_provider, "health_check", healthy)
    client = TestClient(tts_app.app)
    assert client.get("/api/v1/health/ready").json()["provider"]["reachable"] is True
    assert client.get("/api/v1/health/ready").json()["status"] == "ready"
    assert len(calls) == 1


def test_readiness_reports_unreachable_provider(monkeypatch):
    async def unhealthy():
        return False

    monkeypatch.setattr(tts_app.edge_provider, "health_check", unhealthy)
    response = TestClient(tts_app.app).get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["application"] == "alive"
    assert response.json()["provider"]["configured"] is True
    assert response.json()["provider"]["reachable"] is False
    assert response.json()["status"] == "degraded"


def test_readiness_timeout_is_degraded(monkeypatch):
    async def slow():
        await asyncio.sleep(0.1)
        return True

    monkeypatch.setattr(tts_app, "HEALTH_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(tts_app.edge_provider, "health_check", slow)
    response = TestClient(tts_app.app).get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["provider"]["status"] == "timeout"


def test_edge_health_check_uses_upstream_voice_list(monkeypatch):
    async def voice_list():
        return [{"Name": "so-SO-MuuseNeural"}, {"Name": "so-SO-UbaxNeural"}]

    monkeypatch.setattr(tts_app.edge_tts, "list_voices", voice_list)
    assert asyncio.run(tts_app.edge_provider.health_check()) is True


def test_capability_voices_remain_accurate():
    provider = TestClient(tts_app.app).get("/api/v1/capabilities").json()["providers"][0]
    assert [(voice["name"], voice["id"]) for voice in provider["voices"]] == [
        ("Muuse", "so-SO-MuuseNeural"), ("Ubax", "so-SO-UbaxNeural")
    ]


def test_cors_allows_configured_development_origin():
    response = TestClient(tts_app.app).get(
        "/api/v1/health", headers={"Origin": "http://localhost:3000"}
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_rejects_unlisted_origin():
    response = TestClient(tts_app.app).get(
        "/api/v1/health", headers={"Origin": "https://unlisted.example"}
    )
    assert "access-control-allow-origin" not in response.headers


def test_cors_configuration_rejects_wildcard():
    with pytest.raises(ValueError):
        tts_app.parse_cors_origins("*")


def test_request_id_generated_and_safe_incoming_id_preserved():
    client = TestClient(tts_app.app)
    generated = client.get("/api/v1/health").headers["x-request-id"]
    provided = client.get("/api/v1/health", headers={"X-Request-ID": "client_req-123"})
    assert generated
    assert provided.headers["x-request-id"] == "client_req-123"
    invalid = client.get("/api/v1/health", headers={"X-Request-ID": "bad id\r\n"})
    assert invalid.headers["x-request-id"] != "bad id\r\n"


def test_json_logs_do_not_contain_submitted_text(caplog):
    secret_text = "UNIQUE_PRIVATE_TEXT_92831"
    with caplog.at_level(logging.INFO, logger="somalitts"):
        response = TestClient(tts_app.app).post("/tts", data={"text": secret_text})
    assert response.status_code == 200
    entries = [json.loads(record.message) for record in caplog.records if record.name == "somalitts"]
    request_entry = next(item for item in entries if item["event"] == "http_request")
    assert {"method", "path", "status", "duration_ms", "request_id"} <= request_entry.keys()
    assert secret_text not in caplog.text


def test_rate_limit_returns_429_and_retry_after(monkeypatch):
    monkeypatch.setattr(tts_app, "RATE_LIMIT_REQUESTS", 1)
    client = TestClient(tts_app.app)
    assert client.post("/tts", data={"text": "one"}).status_code == 200
    response = client.post("/tts", data={"text": "two"})
    assert response.status_code == 429
    assert response.headers["retry-after"]
    assert response.json()["error"]["code"] == "rate_limit_exceeded"


def test_concurrency_timeout_returns_503_and_releases_slot(monkeypatch):
    monkeypatch.setattr(tts_app, "CONCURRENCY_WAIT_SECONDS", 0.01)
    tts_app._synthesis_semaphore = asyncio.Semaphore(1)
    tts_app._synthesis_semaphore._value = 0
    response = TestClient(tts_app.app).post("/tts", data={"text": "Nabad"})
    assert response.status_code == 503
    assert response.headers["retry-after"] == "2"


def test_provider_error_retries_single_transient_failure():
    FakeCommunicate.fail_once = True
    response = TestClient(tts_app.app).post("/tts", data={"text": "Nabad"})
    assert response.status_code == 200
    assert len(FakeCommunicate.calls) == 2


def test_permanent_provider_failure_is_not_retried():
    FakeCommunicate.fail = True
    response = TestClient(tts_app.app).post("/tts", data={"text": "Nabad"})
    assert response.status_code == 502
    assert len(FakeCommunicate.calls) == 1
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]


def test_existing_synthesis_contract_muuse_ubax_and_chunking():
    client = TestClient(tts_app.app)
    male = client.post("/tts", data={"text": "Nabad", "gender": "male"})
    female = client.post("/tts", data={"text": "Nabad", "gender": "female"})
    assert male.headers["content-type"] == "audio/mpeg"
    assert male.headers["content-disposition"].endswith('filename="somali_voice.mp3"')
    assert FakeCommunicate.calls[:2] == [
        ("Nabad", "so-SO-MuuseNeural"), ("Nabad", "so-SO-UbaxNeural")
    ]

    FakeCommunicate.calls = []
    text = "Af Soomaali waa luqad qurux badan. " * 100
    response = client.post("/tts", data={"text": text})
    assert response.status_code == 200
    assert "".join(part for part, _ in FakeCommunicate.calls) == text


def test_semaphore_is_released_after_provider_exception():
    FakeCommunicate.fail = True
    client = TestClient(tts_app.app)
    assert client.post("/tts", data={"text": "first"}).status_code == 502
    FakeCommunicate.fail = False
    assert client.post("/tts", data={"text": "second"}).status_code == 200


def test_validation_errors_use_safe_error_contract():
    response = TestClient(tts_app.app).post("/tts", data={"gender": "male"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]
