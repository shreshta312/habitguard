from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


CALIBRATION_HISTORY = [30, 40, 35, 45, 50]

STABLE_HISTORY = [
    30, 35, 40, 32, 38,
    41, 36, 39, 42, 37,
    38
]

HEAVY_HISTORY = [
    30, 35, 40, 32, 38,
    41, 36, 39, 42, 37,
    95, 110, 120
]


def test_calibration_mode_returns_no_intervention():
    response = client.post(
        "/habitguard/custom/intervention",
        json={
            "usage_history_minutes": CALIBRATION_HISTORY
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["mode"] == "CALIBRATION"
    assert data["timer_active"] is False
    assert data["should_intervene"] is False
    assert data["friction_type"] == "NONE"
    assert data["recommended_timer_minutes"] is None


def test_active_heavy_usage_triggers_intervention():
    response = client.post(
        "/habitguard/custom/intervention",
        json={
            "usage_history_minutes": HEAVY_HISTORY
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["mode"] == "ACTIVE"
    assert data["timer_active"] is True
    assert data["should_intervene"] is True
    assert data["friction_type"] != "NONE"
    assert data["overuse_gap_minutes"] > 0


def test_temptation_context_triggers_intervention():
    response = client.post(
        "/habitguard/custom/intervention",
        json={
            "usage_history_minutes": STABLE_HISTORY,
            "context": {
                "current_domain": "youtube.com",
                "current_category": "temptation",
                "session_minutes": 20
            }
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["mode"] == "ACTIVE"
    assert data["should_intervene"] is True
    assert data["context_used"]["current_domain"] == "youtube.com"
    assert data["context_used"]["current_category"] == "temptation"


def test_productive_context_softens_intervention():
    heavy_response = client.post(
        "/habitguard/custom/intervention",
        json={
            "usage_history_minutes": HEAVY_HISTORY
        }
    )

    productive_response = client.post(
        "/habitguard/custom/intervention",
        json={
            "usage_history_minutes": HEAVY_HISTORY,
            "context": {
                "current_domain": "leetcode.com",
                "current_category": "productive",
                "session_minutes": 30
            }
        }
    )

    assert heavy_response.status_code == 200
    assert productive_response.status_code == 200

    heavy_data = heavy_response.json()
    productive_data = productive_response.json()

    friction_rank = {
        "NONE": 0,
        "SOFT_WARNING": 1,
        "TIMER_WARNING": 2,
        "STRONG_FRICTION": 3
    }

    assert friction_rank[productive_data["friction_type"]] <= friction_rank[heavy_data["friction_type"]]


def test_response_has_required_keys():
    response = client.post(
        "/habitguard/custom/intervention",
        json={
            "usage_history_minutes": HEAVY_HISTORY
        }
    )

    assert response.status_code == 200

    data = response.json()

    required_keys = [
        "mode",
        "timer_active",
        "usage_status",
        "friction_type",
        "recommended_timer_minutes",
        "overuse_gap_minutes",
        "baseline_usage_minutes",
        "recent_usage_minutes",
        "rho_user",
        "intervention_type",
        "should_intervene",
        "decision_reason",
        "message",
        "context_used",
        "feedback_adaptation_used",
        "feedback_adaptation_reason"
    ]

    for key in required_keys:
        assert key in data

def test_empty_usage_history_returns_no_data_response():
    response = client.post(
        "/habitguard/custom/intervention",
        json={
            "usage_history_minutes": []
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["mode"] == "NO_DATA"
    assert data["timer_active"] is False
    assert data["should_intervene"] is False
    assert data["friction_type"] == "NONE"
    assert data["recommended_timer_minutes"] is None
    assert "error" in data

def test_user_intervention_endpoint_returns_response():
    response = client.get("/habitguard/user/1000/intervention")

    assert response.status_code == 200

    data = response.json()

    assert data is not None
    assert isinstance(data, dict)
    assert "user_id" in data or "error" in data