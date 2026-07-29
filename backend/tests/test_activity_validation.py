"""
test_activity_validation.py

Comprehensive tests for backend activity timestamp, duration, idempotency, and 4xx validation responses.
"""
import pytest
import uuid
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.services.focused_usage_tracker import FocusedUsageTracker
from app.services.session_intent_service import SessionIntentService

client = TestClient(app)


@pytest.fixture
def tracker_and_intent():
    intent_service = SessionIntentService()
    tracker = FocusedUsageTracker()
    return tracker, intent_service


def test_valid_timestamp_after_session_start(tracker_and_intent):
    tracker, intent_service = tracker_and_intent
    session = intent_service.start_session("ts_user_1", "youtube.com", "entertainment", 30.0)
    session_id = session["session_id"]

    event = {
        "event_type": "focus_heartbeat",
        "focused_duration_ms": 60000,
        "client_event_id": f"evt_valid_{uuid.uuid4().hex[:8]}",
        "event_timestamp_utc": datetime.now(timezone.utc).isoformat()
    }
    res = tracker.process_activities(session_id, "ts_user_1", "youtube.com", [event])
    assert res["events_rejected"] == 0
    assert res["events_added"] == 1


def test_reject_events_predating_session_start(tracker_and_intent):
    tracker, intent_service = tracker_and_intent
    session = intent_service.start_session("ts_user_2", "youtube.com", "entertainment", 25.0)
    session_id = session["session_id"]

    past_event = {
        "event_type": "focus_heartbeat",
        "focused_duration_ms": 60000,
        "client_event_id": f"evt_old_{uuid.uuid4().hex[:8]}",
        "event_timestamp_utc": "2024-01-01T00:00:00Z"
    }

    res = tracker.process_activities(session_id, "ts_user_2", "youtube.com", [past_event])
    assert res["events_rejected"] == 1
    assert res["events_added"] == 0


def test_endpoint_returns_400_for_past_event():
    start_res = client.post("/sessions/start", json={
        "user_id": "ts_api_user_1",
        "domain": "youtube.com",
        "purpose": "entertainment",
        "intended_minutes": 20.0
    })
    session_id = start_res.json()["session_id"]

    bad_res = client.post(f"/sessions/{session_id}/activity/batch", json={
        "activities": [{
            "event_type": "focus_heartbeat",
            "focused_duration_ms": 60000,
            "client_event_id": f"evt_past_{uuid.uuid4().hex[:8]}",
            "event_timestamp_utc": "2020-01-01T00:00:00Z"
        }]
    })
    assert bad_res.status_code == 400
    assert "Invalid activity timestamp" in bad_res.json()["detail"]


def test_reject_implausibly_future_events(tracker_and_intent):
    tracker, intent_service = tracker_and_intent
    session = intent_service.start_session("ts_user_3", "youtube.com", "entertainment", 25.0)
    session_id = session["session_id"]

    future_event = {
        "event_type": "focus_heartbeat",
        "focused_duration_ms": 60000,
        "client_event_id": f"evt_future_{uuid.uuid4().hex[:8]}",
        "event_timestamp_utc": "2035-01-01T00:00:00Z"
    }

    res = tracker.process_activities(session_id, "ts_user_3", "youtube.com", [future_event])
    assert res["events_rejected"] == 1
    assert res["events_added"] == 0


def test_reject_excessive_or_zero_duration_event(tracker_and_intent):
    tracker, intent_service = tracker_and_intent
    session = intent_service.start_session("ts_user_4", "youtube.com", "entertainment", 25.0)
    session_id = session["session_id"]

    zero_event = {
        "event_type": "focus_heartbeat",
        "focused_duration_ms": 0,
        "client_event_id": f"evt_zero_{uuid.uuid4().hex[:8]}",
        "event_timestamp_utc": datetime.now(timezone.utc).isoformat()
    }
    huge_event = {
        "event_type": "focus_heartbeat",
        "focused_duration_ms": 18000000,
        "client_event_id": f"evt_huge_{uuid.uuid4().hex[:8]}",
        "event_timestamp_utc": datetime.now(timezone.utc).isoformat()
    }

    res_zero = tracker.process_activities(session_id, "ts_user_4", "youtube.com", [zero_event])
    assert res_zero["events_rejected"] == 1

    res_huge = tracker.process_activities(session_id, "ts_user_4", "youtube.com", [huge_event])
    assert res_huge["events_rejected"] == 1


def test_idempotent_duplicate_event_handling(tracker_and_intent):
    tracker, intent_service = tracker_and_intent
    session = intent_service.start_session("ts_user_5", "youtube.com", "entertainment", 25.0)
    session_id = session["session_id"]

    same_event_id = f"evt_dup_{uuid.uuid4().hex[:8]}"
    event = {
        "event_type": "focus_heartbeat",
        "focused_duration_ms": 60000,
        "client_event_id": same_event_id,
        "event_timestamp_utc": datetime.now(timezone.utc).isoformat()
    }

    res1 = tracker.process_activities(session_id, "ts_user_5", "youtube.com", [event])
    assert res1["events_added"] == 1
    assert res1["total_focused_minutes"] == 1.0

    # Send exact same event ID again
    res2 = tracker.process_activities(session_id, "ts_user_5", "youtube.com", [event])
    assert res2["events_added"] == 0
    assert res2["events_rejected"] == 0
    # Total focused time should NOT be duplicated
    assert res2["total_focused_minutes"] == 1.0


def test_small_allowed_clock_skew(tracker_and_intent):
    tracker, intent_service = tracker_and_intent
    session = intent_service.start_session("ts_user_6", "youtube.com", "entertainment", 25.0)
    session_id = session["session_id"]

    # 2 minutes prior to session start (within 5-min skew tolerance)
    session_start_dt = datetime.fromisoformat(str(session["started_at_utc"]))
    if session_start_dt.tzinfo is None:
        session_start_dt = session_start_dt.replace(tzinfo=timezone.utc)
    skewed_ts = (session_start_dt - timedelta(minutes=2)).isoformat()

    skew_event = {
        "event_type": "focus_heartbeat",
        "focused_duration_ms": 60000,
        "client_event_id": f"evt_skew_{uuid.uuid4().hex[:8]}",
        "event_timestamp_utc": skewed_ts
    }

    res = tracker.process_activities(session_id, "ts_user_6", "youtube.com", [skew_event])
    assert res["events_rejected"] == 0
    assert res["events_added"] == 1
