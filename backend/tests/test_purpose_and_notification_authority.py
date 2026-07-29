import uuid
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_purpose_persists_across_three_consecutive_activity_responses():
    """
    Test 1: Three consecutive activity batch responses for the same episode_id
    must retain the purpose 'entertainment' and canonical intent object.
    """
    user_id = f"test_user_{uuid.uuid4().hex[:6]}"
    domain = "youtube.com"

    # Start session with purpose = entertainment, plan = 10 min
    start_res = client.post("/sessions/start", json={
        "user_id": user_id,
        "domain": domain,
        "purpose": "entertainment",
        "intended_minutes": 10.0,
        "timer_mode": "planned"
    })
    assert start_res.status_code == 200
    session_data = start_res.json()
    session_id = session_data["session_id"]
    episode_id = session_data["episode_id"]

    for i in range(1, 4):
        batch_res = client.post(f"/sessions/{session_id}/activity/batch", json={
            "activities": [{
                "event_type": "focus_heartbeat",
                "focused_duration_ms": 60000 * i,
                "client_event_id": f"evt_{i}_{uuid.uuid4().hex[:6]}",
                "event_timestamp_utc": datetime.now(timezone.utc).isoformat()
            }]
        })
        assert batch_res.status_code == 200
        data = batch_res.json()
        assert data["episode_id"] == episode_id
        assert "intent" in data
        assert data["intent"]["purpose"] == "entertainment"
        assert data["intent"]["effective_planned_minutes"] == 10.0
        assert data["classification"] == "entertainment"

def test_short_switch_resumes_same_episode_and_retains_purpose():
    """
    Test 2: Short switch (gap <= 5 min) resumes the same episode_id and retains purpose/plan.
    """
    user_id = f"test_user_{uuid.uuid4().hex[:6]}"
    domain = "youtube.com"

    s1 = client.post("/sessions/start", json={
        "user_id": user_id,
        "domain": domain,
        "purpose": "entertainment",
        "intended_minutes": 10.0,
        "timer_mode": "planned"
    }).json()

    # Resume session shortly after
    s2 = client.post("/sessions/start", json={
        "user_id": user_id,
        "domain": domain,
        "purpose": "unknown",
        "intended_minutes": None
    }).json()

    assert s2["episode_id"] == s1["episode_id"]
    assert s2["intent"]["purpose"] == "entertainment"
    assert (s2["intent"].get("intended_minutes") == 10.0 or s2["intent"].get("original_intended_minutes") == 10.0)

def test_manual_analyze_automatic_heartbeat_manual_analyze_sequence():
    """
    Test 5/Sequence: Purpose remains entertainment across Manual Analyze -> Automatic Heartbeat -> Manual Analyze
    """
    user_id = f"test_user_{uuid.uuid4().hex[:6]}"
    domain = "youtube.com"

    s1 = client.post("/sessions/start", json={
        "user_id": user_id,
        "domain": domain,
        "purpose": "entertainment",
        "intended_minutes": 10.0,
        "timer_mode": "planned"
    }).json()
    session_id = s1["session_id"]
    episode_id = s1["episode_id"]

    # Step 1: Manual Analyze 1
    r1 = client.post(f"/sessions/{session_id}/activity/batch", json={"activities": []}).json()
    assert r1["episode_id"] == episode_id
    assert r1["intent"]["purpose"] == "entertainment"

    # Step 2: Automatic Heartbeat (1 min focused)
    r2 = client.post(f"/sessions/{session_id}/activity/batch", json={
        "activities": [{
            "event_type": "focus_heartbeat",
            "focused_duration_ms": 60000,
            "client_event_id": f"evt_hb_{uuid.uuid4().hex[:6]}",
            "event_timestamp_utc": datetime.now(timezone.utc).isoformat()
        }]
    }).json()
    assert r2["episode_id"] == episode_id
    assert r2["intent"]["purpose"] == "entertainment"

    # Step 3: Manual Analyze 2
    r3 = client.post(f"/sessions/{session_id}/activity/batch", json={"activities": []}).json()
    assert r3["episode_id"] == episode_id
    assert r3["intent"]["purpose"] == "entertainment"

def test_delivery_trace_endpoint_records_contract_fields():
    """
    Test 6-12: Delivery trace endpoint accepts and records contract fields including requested_channel,
    fallback_channel, intervention_preserved, cooldown_source, next_eligible_at.
    """
    decision_id = f"dec_{uuid.uuid4().hex[:8]}"
    session_id = f"sess_{uuid.uuid4().hex[:8]}"
    episode_id = f"ep_{uuid.uuid4().hex[:8]}"

    # Test API_ACCEPTED trace
    res = client.post("/jitai/delivery-trace", json={
        "decision_id": decision_id,
        "session_id": session_id,
        "episode_id": episode_id,
        "user_id": "local_user",
        "domain": "youtube.com",
        "channel": "notification",
        "requested_channel": "notification",
        "fallback_channel": None,
        "intervention_preserved": True,
        "should_notify": True,
        "should_overlay": False,
        "eligible": True,
        "attempted_at_utc": datetime.now(timezone.utc).isoformat(),
        "delivery_status": "API_ACCEPTED",
        "chrome_notification_id": "hg_notif_123",
        "failure_reason": None,
        "cooldown_source": "VERSIONED_DEFAULT",
        "next_eligible_at": datetime.now(timezone.utc).isoformat()
    })
    assert res.status_code == 200
    trace = res.json()["trace"]
    assert trace["delivery_status"] == "API_ACCEPTED"
    assert trace["requested_channel"] == "notification"
    assert trace["intervention_preserved"] == 1

    # Test PERMISSION_DENIED fallback trace
    res_denied = client.post("/jitai/delivery-trace", json={
        "decision_id": f"dec_denied_{uuid.uuid4().hex[:6]}",
        "session_id": session_id,
        "episode_id": episode_id,
        "user_id": "local_user",
        "domain": "youtube.com",
        "channel": "notification",
        "requested_channel": "notification",
        "fallback_channel": "badge_popup",
        "intervention_preserved": True,
        "should_notify": True,
        "should_overlay": False,
        "eligible": True,
        "attempted_at_utc": datetime.now(timezone.utc).isoformat(),
        "delivery_status": "PERMISSION_DENIED",
        "chrome_notification_id": None,
        "failure_reason": "chrome.notifications API missing or permission denied"
    })
    assert res_denied.status_code == 200
    trace_denied = res_denied.json()["trace"]
    assert trace_denied["delivery_status"] == "PERMISSION_DENIED"
    assert trace_denied["fallback_channel"] == "badge_popup"
    assert trace_denied["intervention_preserved"] == 1
