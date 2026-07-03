from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_usage_snapshot_endpoint():
    payload = {
        "user_id": "usage_test_user",
        "date": "2026-07-03",
        "daily_usage_minutes": {
            "2026-07-03": 85
        },
        "domain_usage_minutes": {
            "2026-07-03": {
                "youtube.com": 40,
                "leetcode.com": 25,
                "github.com": 20
            }
        },
        "current_session": {
            "domain": "youtube.com",
            "category": "temptation",
            "sessionMinutes": 18
        },
        "session_history": [
            {
                "domain": "youtube.com",
                "category": "temptation",
                "durationMinutes": 18
            },
            {
                "domain": "leetcode.com",
                "category": "productive",
                "durationMinutes": 25
            }
        ],
        "latest_intervention": {
            "usage_status": "TEMPTATION_OVERUSE",
            "friction_type": "TIMER_WARNING",
            "intervention_type": "TIMER_NUDGE",
            "should_intervene": True
        },
        "active_intervention_timer": None,
        "source": "chrome_extension"
    }

    response = client.post("/usage/snapshot", json=payload)

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert "snapshot_id" in data


def test_usage_summary_endpoint():
    response = client.get("/usage/summary/usage_test_user")

    assert response.status_code == 200

    data = response.json()

    assert data["user_id"] == "usage_test_user"
    assert "total_snapshots" in data
    assert data["dashboard_ready"] is True
    assert "usage_trend_7_days" in data
    assert "top_domains_today" in data
    assert "top_domains_all_time" in data
    assert "session_stats" in data
    assert "intervention_stats" in data
    assert "extension_event_stats" in data


def test_usage_history_endpoint():
    response = client.get("/usage/history/usage_test_user?limit=5")

    assert response.status_code == 200

    data = response.json()

    assert data["user_id"] == "usage_test_user"
    assert "snapshots" in data
    assert data["limit"] == 5