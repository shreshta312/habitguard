"""
test_display_vs_episode_aggregation.py

Automated tests for Controlled Tests A, B, C, D, E:
- Technical session usage vs Episode-focused usage
- NEAR_PLAN and OVER_PLAN transitions
- Popup display authority (canonical episode_focused_minutes wins)
"""
import pytest
import uuid
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from app.main import app, sessions_repo

client = TestClient(app)


def test_controlled_tests_a_through_e():
    uid = f"user_agg_{uuid.uuid4().hex[:6]}"
    now_dt = datetime.now(timezone.utc)
    t0_iso = (now_dt - timedelta(seconds=600)).isoformat()
    t1_iso = (now_dt - timedelta(seconds=400)).isoformat()

    # --- Test A: ep_1 created with Y1, 2 focused minutes added ---
    s1 = client.post("/sessions/start", json={
        "user_id": uid,
        "domain": "youtube.com",
        "purpose": "entertainment",
        "intended_minutes": 3.0,
        "timer_mode": "planned"
    }).json()
    ep1_id = s1["intent"]["episode_id"]
    y1_sid = s1["session_id"]

    # Y1 usage = 2 minutes (120,000 ms)
    client.post(f"/sessions/{y1_sid}/activity/batch", json={
        "activities": [{
            "client_event_id": f"evt_agg_1_{uuid.uuid4().hex[:6]}",
            "focused_duration_ms": 120000,
            "event_timestamp_utc": now_dt.isoformat()
        }]
    })

    # Y1 closes on short switch
    two_min_ago = (now_dt - timedelta(minutes=2)).isoformat()
    sessions_repo.set_unfocused_timestamp(y1_sid, timestamp_utc=two_min_ago)

    # Return after 2 min -> Y2 starts with same ep1_id
    s2 = client.post("/sessions/start", json={"user_id": uid, "domain": "youtube.com"}).json()
    y2_sid = s2["session_id"]
    assert s2["intent"]["episode_id"] == ep1_id, "Episode ep1_id must be restored on short switch"

    # Batch call for Y2 before new activity
    res_a = client.post(f"/sessions/{y2_sid}/activity/batch", json={"activities": []}).json()
    assert res_a["technical_session_focused_minutes"] == 0.0, "Technical session Y2 usage starts at 0"
    assert res_a["episode_focused_minutes"] == 2.0, "Episode ep_1 usage must equal 2"
    assert res_a["used_minutes"] == 2.0

    # --- Test B: Add 1 minute to Y2 ---
    res_b = client.post(f"/sessions/{y2_sid}/activity/batch", json={
        "activities": [{
            "client_event_id": f"evt_agg_2_{uuid.uuid4().hex[:6]}",
            "focused_duration_ms": 60000,
            "event_timestamp_utc": now_dt.isoformat()
        }]
    }).json()

    assert res_b["technical_session_focused_minutes"] == 1.0, "Technical session Y2 usage = 1"
    assert res_b["episode_focused_minutes"] == 3.0, "Episode ep_1 usage = 3"
    assert res_b["used_minutes"] == 3.0

    # --- Test C: Plan = 3, episode usage = 3 -> NEAR_PLAN ---
    assert res_b["effective_planned_minutes"] == 3.0
    assert res_b["session_status"] == "NEAR_PLAN", "Status must be NEAR_PLAN when episode usage equals plan"
    assert res_b["overuse_gap_minutes"] == 0.0
    assert res_b["recommended_remaining"] == 0.0

    # --- Test D: Add 1 more minute -> OVER_PLAN ---
    res_d = client.post(f"/sessions/{y2_sid}/activity/batch", json={
        "activities": [{
            "client_event_id": f"evt_agg_3_{uuid.uuid4().hex[:6]}",
            "focused_duration_ms": 60000,
            "event_timestamp_utc": now_dt.isoformat()
        }]
    }).json()

    assert res_d["episode_focused_minutes"] == 4.0, "Episode ep_1 usage = 4"
    assert res_d["overuse_gap_minutes"] == 1.0, "Overuse gap must equal 1"
    assert res_d["session_status"] == "OVER_PLAN", "Status must be OVER_PLAN when episode usage > plan"

    # --- Test E: Long gap > 5 minutes creates a new episode ---
    seven_min_ago = (now_dt - timedelta(minutes=7)).isoformat()
    sessions_repo.set_unfocused_timestamp(y2_sid, timestamp_utc=seven_min_ago)

    s3 = client.post("/sessions/start", json={"user_id": uid, "domain": "youtube.com"}).json()
    y3_sid = s3["session_id"]
    ep3_id = s3["intent"]["episode_id"]

    assert ep3_id != ep1_id, "Long gap > 5 min must create new episode"

    res_e = client.post(f"/sessions/{y3_sid}/activity/batch", json={"activities": []}).json()
    assert res_e["episode_focused_minutes"] == 0.0, "New episode usage must start at 0"
    assert res_e["session_status"] == "NO_PLAN"
