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

def test_feedback_summary_endpoint():
    response = client.get("/feedback/summary")

    assert response.status_code == 200

    data = response.json()

    assert "total_events" in data
    assert "event_type_counts" in data
    assert "overlay_dismissed_count" in data
    assert "break_accepted_count" in data
    assert "break_acceptance_rate" in data
    assert "most_dismissed_sites" in data
    assert "most_accepted_break_sites" in data

def test_feedback_summary_can_filter_by_user_id():
    payload = {
        "user_id": "filter_test_user",
        "event_type": "overlay_dismissed",
        "site": "youtube.com",
        "category": "temptation",
        "decision": "overlay_dismissed_by_user",
        "reason": "test_user_filter",
        "context": {
            "test": True
        }
    }

    post_response = client.post("/feedback/event", json=payload)
    assert post_response.status_code == 200

    summary_response = client.get("/feedback/summary?user_id=filter_test_user")
    assert summary_response.status_code == 200

    data = summary_response.json()

    assert data["total_events"] >= 1
    assert data["event_type_counts"]["overlay_dismissed"] >= 1