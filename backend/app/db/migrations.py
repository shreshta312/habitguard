import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from app.db.connection import get_db_connection
from app.db.schema import CREATE_TABLES_SQL
from app.core.config import PROJECT_ROOT

def run_migrations(db_path: Path = None):
    """
    Applies DDL schema migrations idempotently, handling table upgrades and importing legacy records.
    """
    conn = get_db_connection(db_path) if db_path else get_db_connection()
    try:
        cur = conn.cursor()
        
        # Check if legacy feedback_events exists without session_id
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='feedback_events'")
        if cur.fetchone():
            cur.execute("PRAGMA table_info(feedback_events)")
            columns = [row[1] for row in cur.fetchall()]
            if "session_id" not in columns:
                cur.execute("DROP TABLE feedback_events")

        # Check if legacy optimization_runs exists without required columns
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='optimization_runs'")
        if cur.fetchone():
            cur.execute("PRAGMA table_info(optimization_runs)")
            columns = [row[1] for row in cur.fetchall()]
            if "session_id" not in columns or "solver_status" not in columns:
                cur.execute("DROP TABLE optimization_runs")

        # Check and migrate intent_episodes columns idempotently
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='intent_episodes'")
        if cur.fetchone():
            cur.execute("PRAGMA table_info(intent_episodes)")
            columns = [row[1] for row in cur.fetchall()]
            if "extension_minutes" not in columns:
                cur.execute("ALTER TABLE intent_episodes ADD COLUMN extension_minutes REAL NOT NULL DEFAULT 0.0")
            if "original_intended_minutes" not in columns:
                cur.execute("ALTER TABLE intent_episodes ADD COLUMN original_intended_minutes REAL")
            if "last_activity_at_utc" not in columns:
                cur.execute("ALTER TABLE intent_episodes ADD COLUMN last_activity_at_utc TEXT")
            if "last_focused_at_utc" not in columns:
                cur.execute("ALTER TABLE intent_episodes ADD COLUMN last_focused_at_utc TEXT")
            if "unfocused_at_utc" not in columns:
                cur.execute("ALTER TABLE intent_episodes ADD COLUMN unfocused_at_utc TEXT")
            if "expiry_reason" not in columns:
                cur.execute("ALTER TABLE intent_episodes ADD COLUMN expiry_reason TEXT")
            if "stop_reminders" not in columns:
                cur.execute("ALTER TABLE intent_episodes ADD COLUMN stop_reminders INTEGER NOT NULL DEFAULT 0")
            if "version" not in columns:
                cur.execute("ALTER TABLE intent_episodes ADD COLUMN version TEXT NOT NULL DEFAULT '2.0.0'")

        # Check and migrate delivery_traces columns idempotently
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='delivery_traces'")
        if cur.fetchone():
            cur.execute("PRAGMA table_info(delivery_traces)")
            columns = [row[1] for row in cur.fetchall()]
            if "requested_channel" not in columns:
                cur.execute("ALTER TABLE delivery_traces ADD COLUMN requested_channel TEXT DEFAULT 'notification'")
            if "fallback_channel" not in columns:
                cur.execute("ALTER TABLE delivery_traces ADD COLUMN fallback_channel TEXT")
            if "intervention_preserved" not in columns:
                cur.execute("ALTER TABLE delivery_traces ADD COLUMN intervention_preserved INTEGER DEFAULT 0")
            if "cooldown_source" not in columns:
                cur.execute("ALTER TABLE delivery_traces ADD COLUMN cooldown_source TEXT DEFAULT 'VERSIONED_DEFAULT'")
            if "next_eligible_at" not in columns:
                cur.execute("ALTER TABLE delivery_traces ADD COLUMN next_eligible_at TEXT")

        with conn:
            conn.executescript(CREATE_TABLES_SQL)
            
            cur.execute("SELECT MAX(version) FROM schema_migrations")
            row = cur.fetchone()
            current_ver = row[0] if row and row[0] is not None else 0

            if current_ver < 1:
                now_utc = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    "INSERT INTO schema_migrations (version, applied_at_utc) VALUES (?, ?)",
                    (1, now_utc)
                )

        _import_legacy_jsonl(conn)
    finally:
        conn.close()

def _import_legacy_jsonl(conn: sqlite3.Connection):
    data_dir = PROJECT_ROOT / "data"
    feedback_jsonl = data_dir / "feedback.jsonl"
    
    if feedback_jsonl.exists():
        try:
            with open(feedback_jsonl, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    record = json.loads(line)
                    user_id = record.get("user_id", "local_user")
                    session_id = record.get("session_id", "legacy_session")
                    action = record.get("action", record.get("feedback_action", "dismiss"))
                    created_at = record.get("timestamp", record.get("created_at", datetime.now(timezone.utc).isoformat()))
                    
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT id FROM feedback_events WHERE session_id = ? AND action = ? AND created_at_utc = ?",
                        (session_id, action, created_at)
                    )
                    if not cur.fetchone():
                        conn.execute(
                            """INSERT INTO feedback_events 
                               (session_id, user_id, action, task_completion, time_sufficient, created_at_utc)
                               VALUES (?, ?, ?, ?, ?, ?)""",
                            (session_id, user_id, action, None, None, created_at)
                        )
            conn.commit()
        except Exception:
            pass
