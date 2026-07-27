from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_live_endpoint() -> None:
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"

