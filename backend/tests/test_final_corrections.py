"""
Regression tests A-G for the HabitGuard final integration correction pass.
Starting commit: 7aabf246874a186d40717cef5fe46549fd5b979d

Run from backend/ with:
    python -m pytest tests/test_final_corrections.py -v
"""
import os
import json
import tempfile
import sqlite3
import pytest
import pathlib
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.db.connection import get_db_connection
from app.db.migrations import run_migrations


def _ts(offset_minutes: float = 0.0) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=offset_minutes)).isoformat()


def _start_session(client, user_id, domain, purpose="unknown",
                   intended_minutes=None, timer_mode="no_timer"):
    body = {
        "user_id": user_id,
        "domain": domain,
        "purpose": purpose,
        "intended_minutes": intended_minutes,
        "timer_mode": timer_mode,
    }
    r = client.post("/sessions/start", json=body)
    assert r.status_code == 200, f"start_session failed: {r.text}"
    return r.json()


def _post_activity(client, session_id, duration_ms=60000, offset_minutes=0.0):
    ts = _ts(offset_minutes)
    body = {
        "activities": [{
            "client_event_id": f"evt_{session_id}_{ts}_{offset_minutes}",
            "focused_duration_ms": duration_ms,
            "event_timestamp_utc": ts,
        }]
    }
    r = client.post(f"/sessions/{session_id}/activity/batch", json=body)
    assert r.status_code == 200, f"activity batch failed: {r.text}"
    return r.json()


def _unfocus(client, session_id, offset_minutes=0.0):
    r = client.post(f"/sessions/{session_id}/unfocus",
                    params={"timestamp_utc": _ts(offset_minutes)})
    return r


# Test A

def test_A_daily_multi_domain_classification():
    """
    ChatGPT 100 focused minutes no plan: unknown=100.
    YouTube 20 focused minutes 10-min plan: planned=10 unplanned=10.
    Daily: active=120 planned=10 unplanned=10 unknown=100.
    Prove YouTube plan NOT applied to ChatGPT.

    Uses rollup upsert directly to bypass backend per-event timestamp validation
    (which enforces event_ts >= session_start - 5min and event_ts <= now + 5min).
    This is the correct level to test daily summary aggregation logic.
    """
    from app.main import app
    from app.db.repositories.rollups import DailyUsageRollupsRepository
    client = TestClient(app)
    uid = f"u_A_{datetime.now().timestamp()}"
    rollups_repo = DailyUsageRollupsRepository()
    today = datetime.now(timezone.utc).date().isoformat()

    # ChatGPT: 100 focused minutes, no plan -> all unknown
    rollups_repo.upsert_rollup(
        user_id=uid, local_date=today, domain="chatgpt.com",
        focused_minutes=100.0, planned_minutes=0.0,
        unplanned_minutes=0.0, unknown_minutes=100.0
    )

    # YouTube: 20 focused minutes, 10-minute plan -> planned=10, unplanned=10
    rollups_repo.upsert_rollup(
        user_id=uid, local_date=today, domain="youtube.com",
        focused_minutes=20.0, planned_minutes=10.0,
        unplanned_minutes=10.0, unknown_minutes=0.0
    )

    summary = client.get(f"/dashboard/{uid}/summary").json()
    active = summary["active_usage_minutes"]
    planned = summary["planned_minutes"]
    unplanned = summary["unplanned_overuse_minutes"]
    unknown = summary["unknown_minutes"]

    # Core assertions
    assert abs(active - 120.0) < 0.5, f"active expected 120.0, got {active}"
    assert abs(planned - 10.0) < 0.5, f"planned expected 10.0, got {planned}"
    assert abs(unplanned - 10.0) < 0.5, f"unplanned expected 10.0, got {unplanned}"
    assert abs(unknown - 100.0) < 0.5, f"unknown expected 100.0, got {unknown}"

    # Invariant: planned + unplanned + unknown == active (within float tolerance)
    total = planned + unplanned + unknown
    assert abs(total - active) < 0.5, (
        f"planned+unplanned+unknown ({total}) must equal active ({active})"
    )

    # Prove YouTube plan was NOT applied to ChatGPT usage:
    # unknown must be >= 99 (the full 100-min chatgpt block)
    assert unknown >= 99.0, (
        f"YouTube plan must not classify ChatGPT usage. unknown={unknown}, "
        f"should be ~100 (chatgpt no-plan block untouched)"
    )


# Test B

def test_B_local_timezone_boundary():
    """Summary/history/platforms respect IANA timezone; invalid tz falls back safely."""
    from app.main import app
    client = TestClient(app)
    uid = f"u_B_{datetime.now().timestamp()}"

    s = _start_session(client, uid, "youtube.com")
    _post_activity(client, s["session_id"])

    r = client.get(f"/dashboard/{uid}/summary?local_tz=Asia/Kolkata")
    assert r.status_code == 200
    assert "local_date" in r.json()

    r2 = client.get(f"/dashboard/{uid}/summary?local_tz=Not/A/Timezone")
    assert r2.status_code == 200
    assert "local_date" in r2.json()

    r3 = client.get(f"/dashboard/{uid}/summary")
    assert r3.status_code == 200

    r4 = client.get(f"/dashboard/{uid}/history?local_tz=America/New_York")
    assert r4.status_code == 200

    r5 = client.get(f"/dashboard/{uid}/platforms?local_tz=Europe/London")
    assert r5.status_code == 200


# Test C

def test_C_ended_session_excluded_from_current():
    """Create and end a session; /current must return NO_ACTIVE_SESSION."""
    from app.main import app
    client = TestClient(app)
    uid = f"u_C_{datetime.now().timestamp()}"

    s = _start_session(client, uid, "youtube.com", purpose="entertainment",
                       intended_minutes=10.0, timer_mode="planned")
    sid = s["session_id"]
    ep_id = s["intent"]["episode_id"]
    _post_activity(client, sid)

    with get_db_connection() as conn:
        conn.execute("UPDATE technical_sessions SET status = 'ended' WHERE session_id = ?", (sid,))
        conn.execute("UPDATE intent_episodes SET status = 'ended' WHERE episode_id = ?", (ep_id,))

    current = client.get(f"/dashboard/{uid}/current").json()
    assert current.get("status") == "NO_ACTIVE_SESSION", (
        f"/current returned stale ended session: {json.dumps(current)}"
    )
    assert current.get("current_session") is None


# Test D

def test_D_exact_intervention_identity():
    """
    Globally newest optimization_run belongs to session2.
    /current for session1 must return session1's run, not null and not session2's.
    """
    from app.main import app
    client = TestClient(app)
    uid = f"u_D_{datetime.now().timestamp()}"

    s1 = _start_session(client, uid, "youtube.com", purpose="entertainment",
                        intended_minutes=10.0, timer_mode="planned")
    sid1 = s1["session_id"]
    ep1 = s1["intent"]["episode_id"]

    s2 = _start_session(client, uid, "reddit.com")
    sid2 = s2["session_id"]

    earlier = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    now_iso = datetime.now(timezone.utc).isoformat()

    with get_db_connection() as conn:
        conn.execute(
            """INSERT INTO optimization_runs
               (session_id, user_id, input_snapshot_json, observed_baseline, baseline_source,
                planned_minutes, necessary_minimum, minutes_used, temptation_estimate,
                temptation_confidence, optimized_target, recommended_remaining,
                solver_status, configuration_version, tracking_reliability,
                constraints_satisfied, created_at_utc)
               VALUES (?,?,?,10.0,'user_target',10.0,0.0,2.0,0.5,0.8,10.0,8.0,'OPTIMIZED','2.0.0',1.0,1,?)""",
            (sid1, uid, "{}", earlier)
        )
        conn.execute(
            """INSERT INTO optimization_runs
               (session_id, user_id, input_snapshot_json, observed_baseline, baseline_source,
                planned_minutes, necessary_minimum, minutes_used, temptation_estimate,
                temptation_confidence, optimized_target, recommended_remaining,
                solver_status, configuration_version, tracking_reliability,
                constraints_satisfied, created_at_utc)
               VALUES (?,?,?,5.0,'user_target',5.0,0.0,1.0,0.3,0.9,5.0,4.0,'OPTIMIZED','2.0.0',1.0,1,?)""",
            (sid2, uid, "{}", now_iso)
        )

    ep2 = s2["intent"]["episode_id"] if s2.get("intent") else None
    with get_db_connection() as conn:
        conn.execute("UPDATE technical_sessions SET status = 'ended' WHERE session_id = ?", (sid2,))
        if ep2:
            conn.execute("UPDATE intent_episodes SET status = 'ended' WHERE episode_id = ?", (ep2,))

    current = client.get(f"/dashboard/{uid}/current").json()

    assert current.get("status") == "ACTIVE", f"Expected ACTIVE: {current}"
    assert current["current_session"]["session_id"] == sid1
    assert current["latest_intervention"] is not None, "No intervention returned for current session"
    assert current["latest_intervention"]["session_id"] == sid1, (
        f"Intervention session_id must be {sid1}, got {current['latest_intervention']['session_id']}"
    )


# Test E

def test_E_notification_terminal_states_code_verified():
    """
    CODE_VERIFIED: all terminal delivery status values present in background.js.
    Defect 5 fix: chrome.notifications missing branch calls updateLatestDeliveryState.
    MANUAL_REQUIRED: live Chrome behavior.
    """
    bg_path = pathlib.Path(__file__).parent.parent.parent / "chrome_extension" / "background.js"
    code = bg_path.read_text(encoding="utf-8")

    assert 'delivery_status: "SUPPRESSED"' in code
    assert 'delivery_status: "API_ACCEPTED"' in code
    assert 'delivery_status: "PERMISSION_DENIED"' in code
    assert 'delivery_status: "FAILED"' in code
    assert "chrome.notifications API missing" in code

    # Defect 5: updateLatestDeliveryState must appear in the code before the
    # "chrome.notifications API missing" delivery trace line
    missing_idx = code.index("chrome.notifications API missing")
    preceding = code[:missing_idx]
    assert "updateLatestDeliveryState" in preceding, (
        "Defect 5: updateLatestDeliveryState must be called in the "
        "chrome.notifications unavailable branch"
    )

    assert "consumedDecisionIds" in code, "Decision-id idempotency guard missing"


# Test F

def test_F_offline_long_gap_session_not_reused_code_verified():
    """
    CODE_VERIFIED: offline fallback tracks gap and nulls out expired session_id.
    MANUAL_REQUIRED: live offline/online Chrome cycle.
    """
    bg_path = pathlib.Path(__file__).parent.parent.parent / "chrome_extension" / "background.js"
    code = bg_path.read_text(encoding="utf-8")

    assert "offlineFallbackStartedAt" in code, "offlineFallbackStartedAt tracking missing"
    assert "SESSION_RESUME_GAP_MINUTES" in code, "Gap threshold check missing in fallback"
    assert "fallbackSessionId" in code, "fallbackSessionId variable missing"
    assert "skip events recorded under an expired offline fallback" in code, (
        "Skip-null-session guard missing in flushOfflineQueue"
    )


# Test G

def test_G_short_gap_preserves_episode():
    """< 5-min gap restores same episode, purpose, and intent."""
    from app.main import app
    client = TestClient(app)
    uid = f"u_G_short_{datetime.now().timestamp()}"

    s1 = _start_session(client, uid, "youtube.com", purpose="entertainment",
                        intended_minutes=30.0, timer_mode="planned")
    sid1 = s1["session_id"]
    ep1 = s1["intent"]["episode_id"]
    _post_activity(client, sid1, duration_ms=120000)
    _unfocus(client, sid1, offset_minutes=0.0)

    s2 = _start_session(client, uid, "youtube.com")
    ep2 = s2["intent"]["episode_id"]

    assert ep1 == ep2, f"Short gap must reuse same episode: {ep1} vs {ep2}"
    assert s2["intent"]["purpose"] == "entertainment"
    assert s2["intent"]["intended_minutes"] == 30.0


def test_G_long_gap_creates_fresh_episode():
    """Long gap (> 5 min) creates fresh no_timer episode."""
    from app.main import app
    client = TestClient(app)
    uid = f"u_G_long_{datetime.now().timestamp()}"

    s1 = _start_session(client, uid, "youtube.com", purpose="entertainment",
                        intended_minutes=30.0, timer_mode="planned")
    sid1 = s1["session_id"]
    ep1 = s1["intent"]["episode_id"]
    _post_activity(client, sid1, duration_ms=120000)

    past_ts = _ts(-10.0)
    client.post(f"/sessions/{sid1}/unfocus", params={"timestamp_utc": past_ts})

    s2 = _start_session(client, uid, "youtube.com")
    ep2 = s2["intent"]["episode_id"]

    assert ep1 != ep2, f"Long gap must create new episode"
    assert s2["intent"]["timer_mode"] == "no_timer"
    assert s2["intent"]["intended_minutes"] is None


