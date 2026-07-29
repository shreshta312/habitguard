import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from app.db.connection import get_db_connection
from app.db.schema import CREATE_TABLES_SQL
from app.core.config import PROJECT_ROOT

def run_migrations(db_path: Path = None):
    """
    Applies DDL schema migrations idempotently, handling object type inspection,
    legacy view cleanup, table column migrations, data preservation, and index creation.
    """
    target_path = db_path
    if not target_path:
        from app.core.config import DB_PATH
        target_path = DB_PATH

    conn = get_db_connection(target_path)
    try:
        cur = conn.cursor()

        # Step 1: Backup real populated existing database if converting schema
        _backup_db_if_populated(target_path, cur)

        # Step 2: Inspect conflicting objects (feedback_events and snapshots) in sqlite_master
        cur.execute("SELECT name, type, sql FROM sqlite_master WHERE name IN ('feedback_events', 'snapshots')")
        master_objects = {row[0]: {"type": row[1], "sql": row[2]} for row in cur.fetchall()}

        # Step 3: Handle feedback_events object
        fb_obj = master_objects.get("feedback_events")
        if fb_obj:
            if fb_obj["type"] == "view":
                _migrate_legacy_view_data(conn, "feedback_events")
            elif fb_obj["type"] == "table":
                cur.execute("PRAGMA table_info(feedback_events)")
                cols = [r[1] for r in cur.fetchall()]
                if "session_id" not in cols:
                    _migrate_legacy_table_data(conn, "feedback_events")
                    cur.execute("DROP TABLE feedback_events")

        # Step 4: Handle snapshots object
        snap_obj = master_objects.get("snapshots")
        if snap_obj and snap_obj["type"] == "view":
            cur.execute("DROP VIEW IF EXISTS snapshots")

        # Step 5: Check legacy optimization_runs table
        cur.execute("SELECT name, type FROM sqlite_master WHERE name='optimization_runs'")
        opt_obj = cur.fetchone()
        if opt_obj and opt_obj[1] == "table":
            cur.execute("PRAGMA table_info(optimization_runs)")
            cols = [r[1] for r in cur.fetchall()]
            if "session_id" not in cols or "solver_status" not in cols:
                cur.execute("DROP TABLE optimization_runs")

        # Step 6: Idempotent column additions
        _ensure_columns(cur)

        # Step 7: Create canonical tables and indexes
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

def _backup_db_if_populated(target_path: Path, cur: sqlite3.Cursor):
    if not target_path or not target_path.exists():
        return
    cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
    row = cur.fetchone()
    table_count = row[0] if row else 0
    if table_count > 0:
        backup_path = target_path.with_name(target_path.name + ".bak")
        if not backup_path.exists():
            try:
                shutil.copy2(target_path, backup_path)
            except Exception:
                pass

def _migrate_legacy_view_data(conn: sqlite3.Connection, view_name: str):
    cur = conn.cursor()
    if view_name == "feedback_events":
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='feedback'")
        if cur.fetchone():
            cur.execute("SELECT event_id, user_id, event_type, timestamp FROM feedback")
            rows = cur.fetchall()
            cur.execute("DROP VIEW IF EXISTS feedback_events")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feedback_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    task_completion INTEGER,
                    time_sufficient INTEGER,
                    created_at_utc TEXT NOT NULL
                )
            """)
            for r in rows:
                event_id, user_id, action, ts = r[0], r[1], r[2], r[3]
                ts = ts or datetime.now(timezone.utc).isoformat()
                conn.execute(
                    """INSERT INTO feedback_events
                       (session_id, user_id, action, created_at_utc)
                       VALUES (?, ?, ?, ?)""",
                    ("legacy_session", user_id or "local_user", action or "unknown", ts)
                )
            conn.commit()

def _migrate_legacy_table_data(conn: sqlite3.Connection, table_name: str):
    cur = conn.cursor()
    if table_name == "feedback_events":
        cur.execute("SELECT * FROM feedback_events")
        rows = cur.fetchall()
        cur.execute("PRAGMA table_info(feedback_events)")
        cols = [r[1] for r in cur.fetchall()]
        if rows and "action" in cols:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feedback_events_canonical (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    task_completion INTEGER,
                    time_sufficient INTEGER,
                    created_at_utc TEXT NOT NULL
                )
            """)
            for r in rows:
                row_dict = dict(zip(cols, r))
                conn.execute(
                    """INSERT INTO feedback_events_canonical
                       (session_id, user_id, action, created_at_utc)
                       VALUES (?, ?, ?, ?)""",
                    (row_dict.get("session_id", "legacy_session"), row_dict.get("user_id", "local_user"), row_dict.get("action", "unknown"), row_dict.get("created_at_utc", datetime.now(timezone.utc).isoformat()))
                )
            conn.commit()

def _ensure_columns(cur: sqlite3.Cursor):
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
