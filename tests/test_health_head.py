from fastapi.testclient import TestClient

from app import app


def test_liveness_supports_get_and_head():
    client = TestClient(app)

    get_response = client.get("/api/v1/health")
    head_response = client.head("/api/v1/health")

    assert get_response.status_code == 200
    assert get_response.json()["status"] == "ok"
    assert head_response.status_code == 200
    assert head_response.content == b""
    assert head_response.headers.get("x-request-id")
