"""
test_intent_and_extensions.py

Tests for semantic requirements:
- Add 5 behavior (effective planned minutes calculation, original intent preservation, accumulation).
- Purpose vs timer mode separation (no_timer is never stored as purpose; default purpose is unknown).
"""
import pytest
import uuid
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_add_5_increases_effective_plan_accumulates_and_preserves_original_intent():
    uid = f"user_ext1_{uuid.uuid4().hex[:6]}"
    dom = f"site-{uuid.uuid4().hex[:6]}.com"
    # 1. Start session with original plan of 3 minutes
    start_res = client.post("/sessions/start", json={
        "user_id": uid,
        "domain": dom,
        "purpose": "entertainment",
        "intended_minutes": 3.0,
        "timer_mode": "planned"
    })
    assert start_res.status_code == 200
    session_id = start_res.json()["session_id"]

    # 2. Record first Add 5 action
    ext1_res = client.post(f"/sessions/{session_id}/action", json={"action": "extend_5"})
    assert ext1_res.status_code == 200
    data1 = ext1_res.json()

    assert data1["original_intended_minutes"] == 3.0
    assert data1["extension_minutes"] == 5.0
    assert data1["effective_planned_minutes"] == 8.0
    assert data1["planned_minutes"] == 8.0

    # 3. Record second Add 5 action (accumulates)
    ext2_res = client.post(f"/sessions/{session_id}/action", json={"action": "extend_5"})
    assert ext2_res.status_code == 200
    data2 = ext2_res.json()

    assert data2["original_intended_minutes"] == 3.0
    assert data2["extension_minutes"] == 10.0
    assert data2["effective_planned_minutes"] == 13.0
    assert data2["planned_minutes"] == 13.0


def test_remaining_and_over_recalculate_with_effective_planned_minutes():
    uid = f"user_ext2_{uuid.uuid4().hex[:6]}"
    dom = f"site-{uuid.uuid4().hex[:6]}.com"
    # Start session with 3 minutes intended
    start_res = client.post("/sessions/start", json={
        "user_id": uid,
        "domain": dom,
        "purpose": "entertainment",
        "intended_minutes": 3.0,
        "timer_mode": "planned"
    })
    session_id = start_res.json()["session_id"]

    # Add 5 minutes extension -> effective plan = 8
    client.post(f"/sessions/{session_id}/action", json={"action": "extend_5"})

    # Send 6 minutes of focused activity (used = 6, effective plan = 8)
    batch_res = client.post(f"/sessions/{session_id}/activity/batch", json={
        "activities": [{
            "event_type": "focus_heartbeat",
            "focused_duration_ms": 360000, # 6 minutes
            "client_event_id": f"evt_ext_{uuid.uuid4().hex[:8]}",
            "event_timestamp_utc": datetime.now(timezone.utc).isoformat()
        }]
    })
    assert batch_res.status_code == 200
    data = batch_res.json()

    assert data["used_minutes"] == 6.0
    assert data["original_intended_minutes"] == 3.0
    assert data["extension_minutes"] == 5.0
    assert data["effective_planned_minutes"] == 8.0
    assert data["planned_minutes"] == 6.0
    # used = 6, effective plan = 8 => remaining = 2, overuse_gap = 0
    assert data["recommended_remaining_minutes"] == 2.0
    assert data["overuse_gap_minutes"] == 0.0
    assert data["session_status"] == "NEAR_PLAN"


def test_missing_purpose_remains_unknown_and_no_timer_not_stored_as_purpose():
    # Before user selection: purpose = unknown, timer_mode = no_timer
    start_res = client.post("/sessions/start", json={
        "user_id": "test_ext_user_3",
        "domain": "chatgpt.com",
        "purpose": "no_timer",
        "intended_minutes": None,
        "timer_mode": "no_timer"
    })
    assert start_res.status_code == 200
    session = start_res.json()
    intent = session.get("intent", {})

    assert intent["purpose"] == "unknown"
    assert intent["timer_mode"] == "no_timer"
    assert intent["intended_minutes"] is None
    assert intent["purpose"] != "no_timer"

    # Updating intent with purpose = "no_timer" must also preserve purpose = "unknown"
    update_res = client.post(f"/sessions/{session['session_id']}/intent", json={
        "purpose": "no_timer",
        "intended_minutes": None,
        "timer_mode": "no_timer"
    })
    assert update_res.status_code == 200
    updated_session = update_res.json()
    updated_intent = updated_session.get("intent", {})
    assert updated_intent["purpose"] == "unknown"
    assert updated_intent["timer_mode"] == "no_timer"
    assert updated_intent["purpose"] != "no_timer"
