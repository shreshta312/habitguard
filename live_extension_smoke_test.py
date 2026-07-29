"""
live_extension_smoke_test.py

Performs a complete live end-to-end session smoke test simulating the Chrome Extension
interaction with the HabitGuard FastAPI backend and SQLite database.
"""
import json
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi.testclient import TestClient

import tempfile

# Ensure root import path
sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

import app.core.config as config
import app.db.connection as db_conn
from app.db.migrations import run_migrations

# Create temporary throwaway database for smoke test isolation
temp_dir = tempfile.TemporaryDirectory()
temp_db_path = Path(temp_dir.name) / "temp_habitguard.db"

# Patch DB_PATH in config and db connection modules
config.DB_PATH = temp_db_path
db_conn.DB_PATH = temp_db_path

# Run migrations on isolated temp database
run_migrations(temp_db_path)

from app.main import app

client = TestClient(app)

def run_live_smoke_test():
    print("=" * 70)
    print("HABITGUARD CANONICAL EXTENSION LIVE SMOKE TEST")
    print("=" * 70)

    # Step 1: Extension starts session (POST /sessions/start)
    start_payload = {
        "user_id": "extension_live_user",
        "domain": "youtube.com",
        "purpose": "entertainment",
        "intended_minutes": 25.0,
        "timer_mode": "planned",
        "remember_today": False
    }
    print("\n1. REQUEST: POST /sessions/start")
    print(json.dumps(start_payload, indent=2))

    start_res = client.post("/sessions/start", json=start_payload)
    assert start_res.status_code == 200, f"Start failed: {start_res.text}"
    session_data = start_res.json()
    session_id = session_data["session_id"]
    print("   RESPONSE (200 OK):")
    print(json.dumps(session_data, indent=2))

    # Step 2: Intent Update (POST /sessions/{id}/intent)
    intent_payload = {
        "purpose": "entertainment",
        "intended_minutes": 30.0,
        "timer_mode": "planned"
    }
    print(f"\n2. REQUEST: POST /sessions/{session_id}/intent")
    print(json.dumps(intent_payload, indent=2))

    intent_res = client.post(f"/sessions/{session_id}/intent", json=intent_payload)
    assert intent_res.status_code == 200
    print("   RESPONSE (200 OK):")
    print(json.dumps(intent_res.json(), indent=2))

    now_iso = datetime.now(timezone.utc).isoformat()

    # Step 3: Focused Activity Batch 1 (POST /sessions/{id}/activity/batch)
    # Simulate 10 minutes of active focused usage
    batch1_payload = {
        "activities": [
            {
                "event_type": "focus_heartbeat",
                "focused_duration_ms": 600000,
                "client_event_id": f"evt_{uuid.uuid4().hex[:8]}",
                "event_timestamp_utc": now_iso
            }
        ]
    }
    print(f"\n3. REQUEST: POST /sessions/{session_id}/activity/batch (Heartbeat 10 min)")
    print(json.dumps(batch1_payload, indent=2))

    batch1_res = client.post(f"/sessions/{session_id}/activity/batch", json=batch1_payload)
    assert batch1_res.status_code == 200, f"Batch 1 failed: {batch1_res.text}"
    batch1_data = batch1_res.json()
    print("   RESPONSE (200 OK):")
    print(json.dumps(batch1_data, indent=2))

    # Step 4: Focused Activity Batch 2 (Heartbeat 25 min -> Total 35 min, overuse of 5 min)
    batch2_payload = {
        "activities": [
            {
                "event_type": "focus_heartbeat",
                "focused_duration_ms": 1500000,
                "client_event_id": f"evt_{uuid.uuid4().hex[:8]}",
                "event_timestamp_utc": now_iso
            }
        ]
    }
    print(f"\n4. REQUEST: POST /sessions/{session_id}/activity/batch (Heartbeat +25 min -> 35 min Total)")

    batch2_res = client.post(f"/sessions/{session_id}/activity/batch", json=batch2_payload)
    assert batch2_res.status_code == 200
    batch2_data = batch2_res.json()
    print("   RESPONSE (200 OK):")
    print(json.dumps(batch2_data, indent=2))

    # Verify canonical response fields
    assert "used_minutes" in batch2_data
    assert "planned_minutes" in batch2_data
    assert "recommended_remaining" in batch2_data
    assert "overuse_gap_minutes" in batch2_data
    print(f"\n   [CANONICAL FIELD VERIFICATION]")
    print(f"   Used: {batch2_data['used_minutes']} min")
    print(f"   Planned: {batch2_data['planned_minutes']} min")
    print(f"   Remaining: {batch2_data['recommended_remaining']} min")
    print(f"   Over: {batch2_data['overuse_gap_minutes']} min")

    # Step 5: User Action - Task Not Finished (POST /sessions/{id}/action)
    action_payload = {
        "action": "task_not_finished",
        "task_completion": "not_completed",
        "time_sufficient": "insufficient"
    }
    print(f"\n5. REQUEST: POST /sessions/{session_id}/action (Task Not Finished)")
    print(json.dumps(action_payload, indent=2))

    action_res = client.post(f"/sessions/{session_id}/action", json=action_payload)
    assert action_res.status_code == 200
    action_data = action_res.json()
    print("   RESPONSE (200 OK):")
    print(json.dumps(action_data, indent=2))

    # Step 6: Query SQLite Database Records
    print("\n" + "=" * 70)
    print("SQLITE DATABASE RECORDS CREATED DURING SESSION")
    print("=" * 70)

    conn = db_conn.get_db_connection(temp_db_path)
    try:
        cur = conn.cursor()

        print("\n--- [technical_sessions] ---")
        cur.execute("SELECT * FROM technical_sessions WHERE session_id = ?", (session_id,))
        row = cur.fetchone()
        if row:
            print(json.dumps(dict(row), indent=2))

        print("\n--- [intent_episodes] ---")
        if row and row["episode_id"]:
            cur.execute("SELECT * FROM intent_episodes WHERE episode_id = ?", (row["episode_id"],))
            ep_row = cur.fetchone()
            if ep_row:
                print(json.dumps(dict(ep_row), indent=2))

        print("\n--- [session_activities] ---")
        cur.execute("SELECT * FROM session_activities WHERE session_id = ?", (session_id,))
        act_rows = [dict(r) for r in cur.fetchall()]
        print(json.dumps(act_rows, indent=2))

        print("\n--- [optimization_runs (Latest)] ---")
        cur.execute("SELECT id, session_id, user_id, minutes_used, planned_minutes, optimized_target, recommended_remaining, solver_status FROM optimization_runs WHERE session_id = ? ORDER BY id DESC LIMIT 1", (session_id,))
        opt_row = cur.fetchone()
        if opt_row:
            print(json.dumps(dict(opt_row), indent=2))

        print("\n--- [feedback_events] ---")
        cur.execute("SELECT * FROM feedback_events WHERE session_id = ?", (session_id,))
        fb_rows = [dict(r) for r in cur.fetchall()]
        print(json.dumps(fb_rows, indent=2))

        print("\n--- [personal_parameters (Adapted)] ---")
        cur.execute("SELECT * FROM personal_parameters WHERE user_id = 'extension_live_user'", ())
        param_rows = [dict(r) for r in cur.fetchall()]
        print(json.dumps(param_rows, indent=2))

        print("\n--- [session_outcomes] ---")
        cur.execute("SELECT * FROM session_outcomes WHERE session_id = ?", (session_id,))
        out_row = cur.fetchone()
        if out_row:
            print(json.dumps(dict(out_row), indent=2))

    finally:
        conn.close()
        try:
            temp_dir.cleanup()
        except Exception:
            pass

    print("\n" + "=" * 70)
    print("LIVE SMOKE TEST PASSED SUCCESSFULLY (TEMP DB ISOLATED)")
    print("=" * 70)

if __name__ == "__main__":
    run_live_smoke_test()
