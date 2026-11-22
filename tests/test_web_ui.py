from fastapi.testclient import TestClient

from app import app


client = TestClient(app)


def test_home_serves_first_party_voice_studio():
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "SomaliTTS" in response.text
    assert 'id="ttsForm"' in response.text
    assert 'id="cloneForm"' in response.text


def test_clone_path_serves_same_first_party_studio():
    response = client.get("/clone")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert 'id="cloneTab"' in response.text
    assert "/api/v1/clone" in response.text
