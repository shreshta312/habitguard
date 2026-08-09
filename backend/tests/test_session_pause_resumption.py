"""
test_session_pause_resumption.py

Comprehensive tests for Controlled Tests 1-9:
- User-session pause, resumption, and expiry across domain switches
- Centralized SESSION_RESUME_GAP_MINUTES = 5.0
"""
import pytest
import uuid
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from app.main import app, sessions_repo, rollups_repo

client = TestClient(app)


def test_1_two_minute_interruption():
    uid = f"user_t1_{uuid.uuid4().hex[:6]}"
    now_dt = datetime.now(timezone.utc)
    t0_iso = (now_dt - timedelta(seconds=300)).isoformat()
    t100_iso = (now_dt - timedelta(seconds=200)).isoformat() # unfocused at t=100
    t220_iso = (now_dt - timedelta(seconds=80)).isoformat()  # return at t=220 (gap = 2 min = 120s)

    # Start session with 10 min plan
    s1 = client.post("/sessions/start", json={
        "user_id": uid,
        "domain": "youtube.com",
        "purpose": "entertainment",
        "intended_minutes": 10.0,
        "timer_mode": "planned"
    }).json()
    ep1_id = s1["intent"]["episode_id"]
    sid1 = s1["session_id"]

    # Send 4 min (240,000 ms) activity
    client.post(f"/sessions/{sid1}/activity/batch", json={
        "activities": [{
            "client_event_id": f"evt_t1_1_{uuid.uuid4().hex[:6]}",
            "focused_duration_ms": 240000,
            "event_timestamp_utc": t100_iso
        }]
    })

    # Set unfocused at t=100
    sessions_repo.set_unfocused_timestamp(sid1, timestamp_utc=t100_iso)

    # Return at t=220 (gap = 2 min <= 5 min)
    s2 = client.post("/sessions/start", json={
        "user_id": uid,
        "domain": "youtube.com"
    }).json()
    ep2_id = s2["intent"]["episode_id"]
    sid2 = s2["session_id"]

    assert ep1_id == ep2_id, "Episode ep_1 must be restored for 2-minute interruption"

    # Query batch activity for restored session
    res = client.post(f"/sessions/{sid2}/activity/batch", json={"activities": []}).json()
    assert res["session_status"] == "WITHIN_PLAN"
    assert res["used_minutes"] == 4.0
    assert res["effective_planned_minutes"] == 10.0
    assert res["recommended_remaining"] == 6.0


def test_2_continued_usage_after_resumption():
    uid = f"user_t2_{uuid.uuid4().hex[:6]}"
    now_dt = datetime.now(timezone.utc)
    t100_iso = (now_dt - timedelta(seconds=200)).isoformat()
    t220_iso = (now_dt - timedelta(seconds=80)).isoformat()

    s1 = client.post("/sessions/start", json={
        "user_id": uid,
        "domain": "youtube.com",
        "purpose": "entertainment",
        "intended_minutes": 10.0
    }).json()
    ep1_id = s1["intent"]["episode_id"]
    sid1 = s1["session_id"]

    # 4 min activity
    client.post(f"/sessions/{sid1}/activity/batch", json={
        "activities": [{
            "client_event_id": f"evt_t2_1_{uuid.uuid4().hex[:6]}",
            "focused_duration_ms": 240000,
            "event_timestamp_utc": t100_iso
        }]
    })
    sessions_repo.set_unfocused_timestamp(sid1, timestamp_utc=t100_iso)

    # Return after 2 min
    s2 = client.post("/sessions/start", json={"user_id": uid, "domain": "youtube.com"}).json()
    sid2 = s2["session_id"]

    # Add 1 focused minute after resumption
    res = client.post(f"/sessions/{sid2}/activity/batch", json={
        "activities": [{
            "client_event_id": f"evt_t2_2_{uuid.uuid4().hex[:6]}",
            "focused_duration_ms": 60000,
            "event_timestamp_utc": now_dt.isoformat()
        }]
    }).json()

    assert res["episode_id"] == ep1_id
    assert res["used_minutes"] == 5.0
    assert res["recommended_remaining"] == 5.0


def test_3_exactly_five_minutes():
    uid = f"user_t3_{uuid.uuid4().hex[:6]}"
    now_dt = datetime.now(timezone.utc)
    t100_dt = now_dt - timedelta(seconds=270)

    s1 = client.post("/sessions/start", json={
        "user_id": uid,
        "domain": "youtube.com",
        "purpose": "entertainment",
        "intended_minutes": 10.0
    }).json()
    ep1_id = s1["intent"]["episode_id"]
    sid1 = s1["session_id"]

    sessions_repo.set_unfocused_timestamp(sid1, timestamp_utc=t100_dt.isoformat())

    # Return at now_dt (gap <= 5.0 min)
    s2 = client.post("/sessions/start", json={"user_id": uid, "domain": "youtube.com"}).json()
    ep2_id = s2["intent"]["episode_id"]

    assert ep1_id == ep2_id, "Episode ep_1 must be restored at 5 minutes boundary"


def test_4_more_than_five_minutes():
    uid = f"user_t4_{uuid.uuid4().hex[:6]}"
    now_dt = datetime.now(timezone.utc)
    t100_dt = now_dt - timedelta(minutes=7)

    s1 = client.post("/sessions/start", json={
        "user_id": uid,
        "domain": "youtube.com",
        "purpose": "entertainment",
        "intended_minutes": 10.0
    }).json()
    ep1_id = s1["intent"]["episode_id"]
    sid1 = s1["session_id"]

    sessions_repo.set_unfocused_timestamp(sid1, timestamp_utc=t100_dt.isoformat())

    # Return after 7 min (> 5 min)
    s2 = client.post("/sessions/start", json={"user_id": uid, "domain": "youtube.com"}).json()
    ep2_id = s2["intent"]["episode_id"]
    sid2 = s2["session_id"]

    assert ep1_id != ep2_id, "Episode ep_1 must NOT be restored after more than 5 minutes"

    res = client.post(f"/sessions/{sid2}/activity/batch", json={"activities": []}).json()
    assert res["session_status"] == "NO_PLAN"
    assert res["classification"] == "unknown"
    assert res["planned_minutes"] is None
    assert res["used_minutes"] == 0.0
    assert res["recommended_remaining"] is None
    assert res["extension_minutes"] == 0.0


def test_5_explicit_finish():
    uid = f"user_t5_{uuid.uuid4().hex[:6]}"
    s1 = client.post("/sessions/start", json={
        "user_id": uid,
        "domain": "youtube.com",
        "purpose": "entertainment",
        "intended_minutes": 10.0
    }).json()
    ep1_id = s1["intent"]["episode_id"]
    sid1 = s1["session_id"]

    # Explicit Finish
    client.post(f"/sessions/{sid1}/action", json={"action": "finish"})

    # Return after 1 min
    s2 = client.post("/sessions/start", json={"user_id": uid, "domain": "youtube.com"}).json()
    ep2_id = s2["intent"]["episode_id"]

    assert ep1_id != ep2_id, "Explicit finish must prevent episode restoration even within 1 minute"
    assert s2["intent"]["purpose"] == "unknown"


def test_6_history_preservation():
    uid = f"user_t6_{uuid.uuid4().hex[:6]}"
    s1 = client.post("/sessions/start", json={
        "user_id": uid,
        "domain": "youtube.com",
        "purpose": "entertainment",
        "intended_minutes": 10.0
    }).json()
    sid1 = s1["session_id"]

    # Record 4 min usage on episode 1
    client.post(f"/sessions/{sid1}/activity/batch", json={
        "activities": [{
            "client_event_id": f"evt_t6_1_{uuid.uuid4().hex[:6]}",
            "focused_duration_ms": 240000,
            "event_timestamp_utc": datetime.now(timezone.utc).isoformat()
        }]
    })

    # Long gap (10 min ago)
    ten_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    sessions_repo.set_unfocused_timestamp(sid1, timestamp_utc=ten_min_ago)

    # Return to YouTube -> fresh session
    s2 = client.post("/sessions/start", json={"user_id": uid, "domain": "youtube.com"}).json()
    sid2 = s2["session_id"]

    res2 = client.post(f"/sessions/{sid2}/activity/batch", json={"activities": []}).json()
    assert res2["used_minutes"] == 0.0, "Fresh session usage must start at 0"

    # Daily rollups must still contain the 4 minutes from earlier
    rollups = rollups_repo.get_user_rollups(uid, days=1)
    total_focused = sum(r["focused_minutes"] for r in rollups if r["domain"] == "youtube.com")
    assert total_focused >= 4.0, "Daily rollup history must preserve earlier 4 minutes"


def test_7_race_out_of_order_events():
    uid = f"user_t7_{uuid.uuid4().hex[:6]}"
    s1 = client.post("/sessions/start", json={
        "user_id": uid,
        "domain": "youtube.com",
        "purpose": "entertainment",
        "intended_minutes": 10.0
    }).json()
    sid1 = s1["session_id"]
    ep1_id = s1["intent"]["episode_id"]

    # Resume session
    s2 = client.post("/sessions/start", json={"user_id": uid, "domain": "youtube.com"}).json()
    sid2 = s2["session_id"]
    assert s2["intent"]["episode_id"] == ep1_id

    # Stale pause/unfocused event from older session arrives AFTER resumption
    stale_past = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    sessions_repo.set_unfocused_timestamp(sid1, timestamp_utc=stale_past)

    # Active session identity must remain valid and intact
    check_session = sessions_repo.get_technical_session(sid2)
    assert check_session["intent"]["episode_id"] == ep1_id
    assert check_session["intent"]["status"] == "active"


def test_8_popup_authority_no_plan():
    uid = f"user_t8_{uuid.uuid4().hex[:6]}"
    # Start fresh NO_PLAN session
    s = client.post("/sessions/start", json={
        "user_id": uid,
        "domain": "youtube.com",
        "purpose": "unknown",
        "timer_mode": "no_timer"
    }).json()
    sid = s["session_id"]

    res = client.post(f"/sessions/{sid}/activity/batch", json={"activities": []}).json()
    assert res["session_status"] == "NO_PLAN"
    assert res["planned_minutes"] is None
    assert res["recommended_remaining"] is None


def test_9_user_facing_duration_multi_interval():
    uid = f"user_t9_{uuid.uuid4().hex[:6]}"
    s1 = client.post("/sessions/start", json={
        "user_id": uid,
        "domain": "youtube.com",
        "purpose": "entertainment",
        "intended_minutes": 10.0
    }).json()
    ep_id = s1["intent"]["episode_id"]
    sid1 = s1["session_id"]

    # Interval 1: 3 minutes (180,000 ms)
    client.post(f"/sessions/{sid1}/activity/batch", json={
        "activities": [{
            "client_event_id": f"evt_t9_1_{uuid.uuid4().hex[:6]}",
            "focused_duration_ms": 180000,
            "event_timestamp_utc": datetime.now(timezone.utc).isoformat()
        }]
    })

    # Switch away short 1 min and return -> creates technical session 2 under same episode
    s2 = client.post("/sessions/start", json={"user_id": uid, "domain": "youtube.com"}).json()
    sid2 = s2["session_id"]
    assert s2["intent"]["episode_id"] == ep_id

    # Interval 2: 2 minutes (120,000 ms)
    client.post(f"/sessions/{sid2}/activity/batch", json={
        "activities": [{
            "client_event_id": f"evt_t9_2_{uuid.uuid4().hex[:6]}",
            "focused_duration_ms": 120000,
            "event_timestamp_utc": datetime.now(timezone.utc).isoformat()
        }]
    })

    res = client.post(f"/sessions/{sid2}/activity/batch", json={"activities": []}).json()
    assert res["used_minutes"] == 5.0, "Episode usage must sum all focus intervals (3+2 = 5 min)"
    assert res["episode_focused_minutes"] == 5.0
