from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_feedback_event_endpoint():
    payload = {
        "user_id": "test_user",
        "event_type": "overlay_dismissed",
        "site": "youtube.com",
        "category": "entertainment",
        "overlay_id": "test_overlay",
        "decision": "overlay_dismissed_by_user",
        "reason": "user_closed_intervention",
        "context": {
            "test": True,
            "session_minutes": 25
        }
    }

    response = client.post("/feedback/event", json=payload)

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert "event_id" in data
    assert data["message"] == "Feedback event saved successfully"