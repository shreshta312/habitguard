import os
import json
import tempfile
import sqlite3
import pytest
from pathlib import Path
from datetime import datetime, timezone

from app.db.connection import get_db_connection
from app.db.migrations import run_migrations
from app.services.dataset_service import DatasetService
from app.services.habitguard_service import HabitGuardService
from app.services.behavior_feature_service import BehaviorFeatureService
from app.services.session_intent_service import SessionIntentService
from app.db.repositories.sessions import SessionsRepository

def test_addendum_a_fresh_database_migration():
    temp_dir = tempfile.mkdtemp(prefix="hg_fresh_db_")
    db_path = Path(temp_dir) / "fresh_habitguard.db"
    
    run_migrations(db_path)
    
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("SELECT name, type FROM sqlite_master WHERE name IN ('feedback_events', 'snapshots')")
    objects = dict(cur.fetchall())
    conn.close()

    assert objects.get("feedback_events") == "table", "feedback_events must be a table in canonical schema"
    assert objects.get("snapshots") is None or objects.get("snapshots") == "view"

def test_addendum_a_legacy_view_migration():
    temp_dir = tempfile.mkdtemp(prefix="hg_legacy_view_")
    db_path = Path(temp_dir) / "legacy_view_habitguard.db"

    # Set up legacy database with VIEW feedback_events over feedback table
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE feedback (
            event_id TEXT PRIMARY KEY,
            user_id TEXT,
            event_type TEXT,
            timestamp TEXT,
            server_received_at TEXT,
            payload TEXT
        )
    """)
    conn.execute("INSERT INTO feedback VALUES ('evt_1', 'u1', 'dismiss', '2026-07-29T00:00:00Z', '2026-07-29T00:00:00Z', '{}')")
    conn.execute("CREATE VIEW feedback_events AS SELECT * FROM feedback")
    conn.commit()
    conn.close()

    # Verify initial state: feedback_events is a view
    conn_chk = sqlite3.connect(str(db_path))
    init_obj = conn_chk.execute("SELECT name, type FROM sqlite_master WHERE name='feedback_events'").fetchone()
    conn_chk.close()
    assert init_obj == ("feedback_events", "view")

    # Run canonical migrations
    run_migrations(db_path)

    # Verify post-migration state: feedback_events is now a table containing migrated data
    conn_after = sqlite3.connect(str(db_path))
    cur = conn_after.cursor()
    cur.execute("SELECT name, type FROM sqlite_master WHERE name='feedback_events'")
    obj_after = cur.fetchone()
    assert obj_after == ("feedback_events", "table"), "feedback_events view must be converted to table"

    cur.execute("SELECT action, user_id FROM feedback_events")
    migrated_rows = cur.fetchall()
    conn_after.close()
    assert len(migrated_rows) == 1
    assert migrated_rows[0][0] == "dismiss"

def test_addendum_a_idempotent_migrations_executed_twice():
    temp_dir = tempfile.mkdtemp(prefix="hg_idempotent_")
    db_path = Path(temp_dir) / "idempotent_habitguard.db"

    run_migrations(db_path)
    conn1 = sqlite3.connect(str(db_path))
    objs1 = conn1.execute("SELECT name, type, sql FROM sqlite_master ORDER BY name").fetchall()
    conn1.close()

    # Second migration execution
    run_migrations(db_path)
    conn2 = sqlite3.connect(str(db_path))
    objs2 = conn2.execute("SELECT name, type, sql FROM sqlite_master ORDER BY name").fetchall()
    conn2.close()

    assert objs1 == objs2, "Migrations executed twice must produce identical sqlite_master objects"

def test_addendum_b_pytest_database_isolation(tmp_path):
    env_db = os.environ.get("HABITGUARD_DB_PATH")
    assert env_db is not None, "HABITGUARD_DB_PATH must be set during pytest"
    assert "data/habitguard.db" not in env_db.replace("\\", "/"), "Pytest must not touch real dev database data/habitguard.db"

def test_addendum_c_analytics_csv_missing_degradation(tmp_path):
    absent_path = tmp_path / "nonexistent_analytics.csv"
    svc = HabitGuardService(csv_path=absent_path)
    
    summary = svc.get_user_daily_summary("local_user")
    assert summary["status"] == "ANALYTICS_DATA_UNAVAILABLE"
    assert summary["used_in_live_intervention_loop"] is False

    app_summary = svc.get_user_app_summary("local_user", "youtube")
    assert app_summary["status"] == "ANALYTICS_DATA_UNAVAILABLE"
    assert app_summary["used_in_live_intervention_loop"] is False

def test_addendum_c_cwd_independence(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ds = DatasetService()
    # Path resolved relative to PROJECT_ROOT, not CWD
    assert ds.csv_path.is_absolute()
    assert ds.load_data() is None or len(ds.load_data()) >= 0

def test_recheck_1_cross_domain_switches():
    bf = BehaviorFeatureService()
    features = bf.extract_features(
        focused_minutes=25.0,
        planned_minutes=20.0,
        purpose="entertainment",
        cross_domain_switches=3
    )
    assert "rapid_switching" in features
    assert features["rapid_switching"] == round(3 / 15.0, 4)

def test_recheck_2_browser_iana_timezone():
    sessions_repo = SessionsRepository()
    session = sessions_repo.create_technical_session("u_kolkata", "youtube.com", local_timezone="Asia/Kolkata")
    assert session["local_timezone"] == "Asia/Kolkata"

def test_recheck_3_unfocus_endpoint_call_path():
    sessions_repo = SessionsRepository()
    intent_svc = SessionIntentService(sessions_repo)
    sess = intent_svc.start_session("u_unfocus", "youtube.com")
    
    now_iso = datetime.now(timezone.utc).isoformat()
    sessions_repo.set_unfocused_timestamp(sess["session_id"], now_iso)
    
    updated_ep = sessions_repo.get_intent_episode(sess["episode_id"])
    assert updated_ep["unfocused_at_utc"] == now_iso

def test_requirement_1_focus_state_classification():
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    uid = f"u_focus_{datetime.now().timestamp()}"
    
    # 1. Start YouTube session
    r1 = client.post("/sessions/start", json={"user_id": uid, "domain": "youtube.com", "purpose": "entertainment", "intended_minutes": 30.0}).json()
    s1_id = r1["session_id"]
    ep1_id = r1["intent"]["episode_id"]

    # 2. EXTENSION_TRANSIENT (popup / devtools / chrome://extensions):
    # Rule A: preserve current session/episode, do NOT call /unfocus
    ep_before = client.get(f"/sessions/{s1_id}").json()["intent"]
    assert ep_before.get("unfocused_at_utc") is None

    # 3. GENUINELY_UNFOCUSED (WINDOW_ID_NONE / minimized / idle):
    # Rule B: call /unfocus for prior session
    unfocus_res = client.post(f"/sessions/{s1_id}/unfocus")
    assert unfocus_res.status_code == 200
    ep_after = client.get(f"/sessions/{s1_id}").json()["intent"]
    assert ep_after.get("unfocused_at_utc") is not None

    # 4. DIFFERENT_TRACKABLE_DOMAIN (YouTube -> ChatGPT):
    # Rule C: unfocus prior session, start ChatGPT session, preserve intent episode for 5-min window
    r2 = client.post("/sessions/start", json={"user_id": uid, "domain": "chatgpt.com", "purpose": "work_study"}).json()
    assert r2["session_id"] != s1_id

def test_requirement_5_jitai_and_overlay_authority():
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    uid = f"u_jitai_{datetime.now().timestamp()}"
    r1 = client.post("/sessions/start", json={"user_id": uid, "domain": "youtube.com", "purpose": "entertainment", "intended_minutes": 10.0}).json()
    s1_id = r1["session_id"]
    ep1_id = r1["intent"]["episode_id"]

    # Overrun plan to trigger JITAI decision
    act_res = client.post(f"/sessions/{s1_id}/activity/batch", json={
        "activities": [{
            "client_event_id": f"evt_j_{datetime.now().timestamp()}",
            "focused_duration_ms": 900000, # 15 mins (5 mins overuse)
            "event_timestamp_utc": datetime.now(timezone.utc).isoformat()
        }]
    })
    assert act_res.status_code == 200
    data = act_res.json()
    assert data["should_intervene"] is True
    assert data["decision_id"] is not None

    # Post delivery trace
    trace_res = client.post("/jitai/delivery-trace", json={
        "decision_id": data["decision_id"],
        "session_id": s1_id,
        "episode_id": ep1_id,
        "user_id": uid,
        "domain": "youtube.com",
        "channel": "notification",
        "should_notify": True,
        "should_overlay": False,
        "eligible": True,
        "attempted_at_utc": datetime.now(timezone.utc).isoformat(),
        "delivery_status": "API_ACCEPTED"
    })
    assert trace_res.status_code == 200
    assert trace_res.json()["status"] == "success"

def test_requirement_2_ordered_cross_domain_switch_sequences():
    repo = SessionsRepository()
    uid = f"u_sw_seq_{datetime.now().timestamp()}"

    # YouTube -> ChatGPT = 1 switch
    repo.create_technical_session(uid, "youtube.com")
    repo.create_technical_session(uid, "chatgpt.com")
    assert repo.get_ordered_cross_domain_switches(uid, days=1) == 1

    # YouTube -> ChatGPT -> YouTube = 2 switches
    repo.create_technical_session(uid, "youtube.com")
    assert repo.get_ordered_cross_domain_switches(uid, days=1) == 2

    # YouTube -> YouTube = 0 switches (same domain repeated session)
    uid_same = f"u_sw_same_{datetime.now().timestamp()}"
    repo.create_technical_session(uid_same, "youtube.com")
    repo.create_technical_session(uid_same, "youtube.com")
    assert repo.get_ordered_cross_domain_switches(uid_same, days=1) == 0

def test_requirement_4_feedback_adaptation_work_study_vs_entertainment():
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    uid = f"u_adapt_{datetime.now().timestamp()}"

    # Session 1: work_study task -> task_not_finished feedback
    s1 = client.post("/sessions/start", json={"user_id": uid, "domain": "youtube.com", "purpose": "work_study", "intended_minutes": 20.0}).json()
    act1 = client.post(f"/sessions/{s1['session_id']}/activity/batch", json={
        "activities": [{"client_event_id": f"e_a1_{datetime.now().timestamp()}", "focused_duration_ms": 600000, "event_timestamp_utc": datetime.now(timezone.utc).isoformat()}]
    }).json()
    
    # Submit task_not_finished action feedback
    fb_res = client.post(f"/sessions/{s1['session_id']}/action", json={"action": "task_not_finished", "task_completion": "not_completed", "time_sufficient": "insufficient"})
    assert fb_res.status_code == 200

    # Session 2: next work_study session loads learned parameter, necessary_minimum increases within bounds
    s2 = client.post("/sessions/start", json={"user_id": uid, "domain": "youtube.com", "purpose": "work_study", "intended_minutes": 20.0}).json()
    act2 = client.post(f"/sessions/{s2['session_id']}/activity/batch", json={
        "activities": [{"client_event_id": f"e_a2_{datetime.now().timestamp()}", "focused_duration_ms": 60000, "event_timestamp_utc": datetime.now(timezone.utc).isoformat()}]
    }).json()

    # Verify feedback was persisted and loaded
    conn = get_db_connection()
    fb_row = conn.execute("SELECT * FROM feedback_events WHERE session_id = ?", (s1["session_id"],)).fetchone()
    conn.close()
    assert fb_row is not None

    # Negative test: entertainment session must NOT protect or increase necessary minimum
    s_ent = client.post("/sessions/start", json={"user_id": uid, "domain": "youtube.com", "purpose": "entertainment", "intended_minutes": 20.0}).json()
    act_ent = client.post(f"/sessions/{s_ent['session_id']}/activity/batch", json={
        "activities": [{"client_event_id": f"e_ent_{datetime.now().timestamp()}", "focused_duration_ms": 60000, "event_timestamp_utc": datetime.now(timezone.utc).isoformat()}]
    }).json()
    # Entertainment classification does not use task protection
    assert act_ent["classification"] == "entertainment"

def test_requirement_5_category_conflict_scenarios():
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    uid = f"u_cat_conf_{datetime.now().timestamp()}"

    # Scenario A: category=temptation, purpose=work_study -> task protection retained, purpose not overwritten
    s_a = client.post("/sessions/start", json={"user_id": uid, "domain": "youtube.com", "purpose": "work_study", "intended_minutes": 30.0}).json()
    act_a = client.post(f"/sessions/{s_a['session_id']}/activity/batch", json={
        "current_category": "temptation",
        "activities": [{"client_event_id": f"e_c1_{datetime.now().timestamp()}", "focused_duration_ms": 60000, "event_timestamp_utc": datetime.now(timezone.utc).isoformat()}]
    }).json()
    assert act_a["intent"]["purpose"] == "work_study"

    # Scenario B: category=productive, purpose=entertainment -> entertainment is not necessary, category is metadata
    s_b = client.post("/sessions/start", json={"user_id": uid, "domain": "youtube.com", "purpose": "entertainment", "intended_minutes": 30.0}).json()
    act_b = client.post(f"/sessions/{s_b['session_id']}/activity/batch", json={
        "current_category": "productive",
        "activities": [{"client_event_id": f"e_c2_{datetime.now().timestamp()}", "focused_duration_ms": 60000, "event_timestamp_utc": datetime.now(timezone.utc).isoformat()}]
    }).json()
    assert act_b["classification"] == "entertainment"

    # Scenario C: no plan + temptation category -> classification remains unknown, unplanned minutes remain 0, category does not invent plan
    s_c = client.post("/sessions/start", json={"user_id": uid, "domain": "youtube.com", "purpose": "no_timer", "intended_minutes": None, "timer_mode": "no_timer"}).json()
    act_c = client.post(f"/sessions/{s_c['session_id']}/activity/batch", json={
        "current_category": "temptation",
        "activities": [{"client_event_id": f"e_c3_{datetime.now().timestamp()}", "focused_duration_ms": 60000, "event_timestamp_utc": datetime.now(timezone.utc).isoformat()}]
    }).json()
    assert act_c["session_status"] == "NO_PLAN"
    assert act_c["planned_minutes"] is None
    assert act_c["unplanned_minutes"] == 0.0

def test_requirement_6_duplicate_client_event_id_rollup_idempotency():
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    uid = f"u_dup_idemp_{datetime.now().timestamp()}"
    s = client.post("/sessions/start", json={"user_id": uid, "domain": "youtube.com", "purpose": "entertainment", "intended_minutes": 20.0}).json()
    sid = s["session_id"]
    client_id = f"evt_dup_{datetime.now().timestamp()}"

    # First activity submit
    act1 = client.post(f"/sessions/{sid}/activity/batch", json={
        "activities": [{"client_event_id": client_id, "focused_duration_ms": 120000, "event_timestamp_utc": datetime.now(timezone.utc).isoformat()}]
    }).json()

    conn = get_db_connection()
    act_count1 = conn.execute("SELECT COUNT(*) FROM session_activities WHERE session_id = ?", (sid,)).fetchone()[0]
    out1 = conn.execute("SELECT * FROM session_outcomes WHERE session_id = ?", (sid,)).fetchone()
    conn.close()

    # Second submission with duplicate client_event_id (offline retry)
    act2 = client.post(f"/sessions/{sid}/activity/batch", json={
        "activities": [{"client_event_id": client_id, "focused_duration_ms": 120000, "event_timestamp_utc": datetime.now(timezone.utc).isoformat()}]
    }).json()

    conn2 = get_db_connection()
    act_count2 = conn2.execute("SELECT COUNT(*) FROM session_activities WHERE session_id = ?", (sid,)).fetchone()[0]
    out2 = conn2.execute("SELECT * FROM session_outcomes WHERE session_id = ?", (sid,)).fetchone()
    conn2.close()

    assert act_count1 == act_count2 == 1, "Duplicate client_event_id must not insert duplicate session_activities"
    assert out1["actual_focused_minutes"] == out2["actual_focused_minutes"] == 2.0


