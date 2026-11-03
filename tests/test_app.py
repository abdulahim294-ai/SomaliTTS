import pytest
from fastapi.testclient import TestClient

import app as tts_app


class FakeCommunicate:
    calls = []
    audio = b"\xff\xfb\x90\x64fake-mp3-frame"
    fail = False

    def __init__(self, text, voice):
        self.calls.append((text, voice))

    async def stream(self):
        if self.fail:
            raise ConnectionError("mock provider failure")
        yield {"type": "audio", "data": self.audio}


def setup_function():
    FakeCommunicate.calls = []
    FakeCommunicate.fail = False
    FakeCommunicate.audio = b"\xff\xfb\x90\x64fake-mp3-frame"
    tts_app.edge_tts.Communicate = FakeCommunicate


def test_health_endpoint_is_liveness_only():
    response = TestClient(tts_app.app).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "SomaliTTS",
        "api_version": "v1",
    }
    assert FakeCommunicate.calls == []


def test_capabilities_report_configured_somali_edge_voices_and_limits():
    response = TestClient(tts_app.app).get("/api/v1/capabilities")

    assert response.status_code == 200
    body = response.json()
    assert body["api_version"] == "v1"
    assert len(body["providers"]) == 1
    provider = body["providers"][0]
    assert provider["id"] == "edge-tts"
    assert provider["configured"] is True
    assert provider["voices"] == [
        {"id": "so-SO-MuuseNeural", "name": "Muuse", "gender": "male", "locale": "so-SO"},
        {"id": "so-SO-UbaxNeural", "name": "Ubax", "gender": "female", "locale": "so-SO"},
    ]
    assert provider["features"] == {
        "text_to_speech": True,
        "voice_cloning": False,
        "public_voice_sharing": False,
        "durable_long_form_jobs": False,
        "emotional_synthesis": False,
    }


def test_capabilities_do_not_claim_unimplemented_features():
    response = TestClient(tts_app.app).get("/api/v1/capabilities")
    assert response.status_code == 200
    features = response.json()["providers"][0]["features"]
    assert features["voice_cloning"] is False
    assert features["public_voice_sharing"] is False
    assert features["durable_long_form_jobs"] is False
    assert features["emotional_synthesis"] is False


def test_selects_male_voice_and_returns_mp3():
    client = TestClient(tts_app.app)
    response = client.post("/tts", data={"text": "Nabad", "gender": "male"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.headers["content-disposition"].endswith('filename="somali_voice.mp3"')
    assert response.content.startswith(b"\xff\xfb")
    assert FakeCommunicate.calls == [("Nabad", "so-SO-MuuseNeural")]


def test_selects_female_voice():
    client = TestClient(tts_app.app)
    response = client.post("/tts", data={"text": "Nabad", "gender": "female"})

    assert response.status_code == 200
    assert FakeCommunicate.calls == [("Nabad", "so-SO-UbaxNeural")]


def test_provider_error_returns_gateway_error():
    FakeCommunicate.fail = True
    response = TestClient(tts_app.app).post("/tts", data={"text": "Nabad"})

    assert response.status_code == 502
    assert "failed to generate audio" in response.json()["detail"]


def test_empty_provider_audio_returns_gateway_error():
    FakeCommunicate.audio = b""
    response = TestClient(tts_app.app).post("/tts", data={"text": "Nabad"})

    assert response.status_code == 502


def test_long_text_is_split_and_all_segments_are_returned():
    text = ("Af Soomaali waa luqad qurux badan. " * 100)
    response = TestClient(tts_app.app).post("/tts", data={"text": text})

    assert response.status_code == 200
    assert len(FakeCommunicate.calls) > 1
    assert "".join(part for part, _ in FakeCommunicate.calls) == text
    assert response.content == FakeCommunicate.audio * len(FakeCommunicate.calls)


def test_rejects_invalid_gender_and_empty_text():
    client = TestClient(tts_app.app)

    assert client.post("/tts", data={"text": "Nabad", "gender": "other"}).status_code == 422
    assert client.post("/tts", data={"text": "   "}).status_code == 422


def test_rejects_text_over_limit():
    response = TestClient(tts_app.app).post(
        "/tts", data={"text": "x" * (tts_app.MAX_TEXT_LENGTH + 1)}
    )

    assert response.status_code == 413
