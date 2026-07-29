"""
test_acceptance_scenarios.py

Automated implementation and verification for the Five Core Acceptance Scenarios:
- Scenario A: No-plan YouTube (NO_PLAN, unknown classification, null overuse gap, null planned minutes)
- Scenario B: Within-plan YouTube (WITHIN_PLAN, recommended remaining, zero overuse gap)
- Scenario C: Over-plan YouTube with delivery trace (OVER_PLAN, should_notify=true, delivery trace persistence)
- Scenario D: Two-minute interruption restores YouTube episode (same episode_id)
- Scenario E: Ten-minute interruption starts fresh NO_PLAN episode (fresh episode_id)
"""
import pytest
import uuid
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_scenario_a_no_plan_youtube():
    uid = f"user_scen_a_{uuid.uuid4().hex[:6]}"
    # Start session with no_timer / no plan
    start_res = client.post("/sessions/start", json={
        "user_id": uid,
        "domain": "youtube.com",
        "purpose": "no_timer",
        "intended_minutes": None,
        "timer_mode": "no_timer"
    })
    assert start_res.status_code == 200
    session_id = start_res.json()["session_id"]

    # Send 5 min activity heartbeat
    act_res = client.post(f"/sessions/{session_id}/activity/batch", json={
        "activities": [{
            "client_event_id": f"evt_a_{uuid.uuid4().hex[:8]}",
            "focused_duration_ms": 300000,
            "event_timestamp_utc": datetime.now(timezone.utc).isoformat()
        }]
    })
    assert act_res.status_code == 200
    data = act_res.json()

    assert data["session_status"] == "NO_PLAN"
    assert data["classification"] == "unknown"
    assert data["planned_minutes"] is None
    assert data["overuse_gap_minutes"] is None
    assert data["recommended_remaining"] is None


def test_scenario_b_within_plan_youtube():
    uid = f"user_scen_b_{uuid.uuid4().hex[:6]}"
    # Start session with 30 minutes plan
    start_res = client.post("/sessions/start", json={
        "user_id": uid,
        "domain": "youtube.com",
        "purpose": "entertainment",
        "intended_minutes": 30.0,
        "timer_mode": "planned"
    })
    assert start_res.status_code == 200
    session_id = start_res.json()["session_id"]

    # Send 10 min activity heartbeat
    act_res = client.post(f"/sessions/{session_id}/activity/batch", json={
        "activities": [{
            "client_event_id": f"evt_b_{uuid.uuid4().hex[:8]}",
            "focused_duration_ms": 600000,
            "event_timestamp_utc": datetime.now(timezone.utc).isoformat()
        }]
    })
    assert act_res.status_code == 200
    data = act_res.json()

    assert data["session_status"] == "WITHIN_PLAN"
    assert data["used_minutes"] == 10.0
    assert data["effective_planned_minutes"] == 30.0
    assert data["recommended_remaining"] == 20.0
    assert data["overuse_gap_minutes"] == 0.0


def test_scenario_c_over_plan_youtube_with_delivery_attempt():
    uid = f"user_scen_c_{uuid.uuid4().hex[:6]}"
    # Start session with 15 minutes plan
    start_res = client.post("/sessions/start", json={
        "user_id": uid,
        "domain": "youtube.com",
        "purpose": "entertainment",
        "intended_minutes": 15.0,
        "timer_mode": "planned"
    })
    assert start_res.status_code == 200
    session = start_res.json()
    session_id = session["session_id"]
    episode_id = session.get("intent", {}).get("episode_id")

    # Send 25 min activity (10 min over plan)
    act_res = client.post(f"/sessions/{session_id}/activity/batch", json={
        "activities": [{
            "client_event_id": f"evt_c_{uuid.uuid4().hex[:8]}",
            "focused_duration_ms": 1500000,
            "event_timestamp_utc": datetime.now(timezone.utc).isoformat()
        }]
    })
    assert act_res.status_code == 200
    data = act_res.json()

    assert data["session_status"] == "OVER_PLAN"
    assert data["overuse_gap_minutes"] == 10.0
    assert data["should_intervene"] is True
    assert data["decision_id"] is not None

    # Post delivery trace to backend
    trace_res = client.post("/jitai/delivery-trace", json={
        "decision_id": data["decision_id"],
        "session_id": session_id,
        "episode_id": episode_id,
        "user_id": uid,
        "domain": "youtube.com",
        "channel": "notification",
        "should_notify": True,
        "should_overlay": False,
        "eligible": True,
        "attempted_at_utc": datetime.now(timezone.utc).isoformat(),
        "delivery_status": "ATTEMPTED",
        "chrome_notification_id": "hg_notif_test_123",
        "failure_reason": None
    })
    assert trace_res.status_code == 200
    trace_data = trace_res.json()
    assert trace_data["status"] == "success"
    assert trace_data["trace"]["delivery_status"] == "ATTEMPTED"


def test_scenario_d_two_minute_interruption_restores_episode():
    uid = f"user_scen_d_{uuid.uuid4().hex[:6]}"
    s1 = client.post("/sessions/start", json={
        "user_id": uid,
        "domain": "youtube.com",
        "purpose": "entertainment",
        "intended_minutes": 30.0
    }).json()
    ep1_id = s1["intent"]["episode_id"]

    # Short 1 min switch to ChatGPT
    s_chat = client.post("/sessions/start", json={
        "user_id": uid,
        "domain": "chatgpt.com",
        "purpose": "work_study"
    }).json()

    # Return to YouTube within 2 min
    s2 = client.post("/sessions/start", json={
        "user_id": uid,
        "domain": "youtube.com"
    }).json()
    ep2_id = s2["intent"]["episode_id"]

    assert ep1_id == ep2_id, "2-minute interruption must restore active episode"


def test_scenario_e_ten_minute_interruption_starts_fresh_no_plan_episode():
    uid = f"user_scen_e_{uuid.uuid4().hex[:6]}"
    s1 = client.post("/sessions/start", json={
        "user_id": uid,
        "domain": "youtube.com",
        "purpose": "entertainment",
        "intended_minutes": 30.0
    }).json()
    ep1_id = s1["intent"]["episode_id"]

    # Set unfocused timestamp 10 min ago via repository set_unfocused_timestamp
    ten_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    from app.main import sessions_repo
    sessions_repo.set_unfocused_timestamp(s1["session_id"], timestamp_utc=ten_min_ago)

    # Return to YouTube after 10 min
    s2 = client.post("/sessions/start", json={
        "user_id": uid,
        "domain": "youtube.com"
    }).json()
    ep2_id = s2["intent"]["episode_id"]

    assert ep1_id != ep2_id, "10-minute interruption must expire old episode and start fresh episode"
    assert s2["intent"]["purpose"] == "unknown", "Fresh episode must start with unknown purpose / NO_PLAN"
