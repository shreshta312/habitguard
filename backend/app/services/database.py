import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager

DATABASE_FILE = Path(__file__).resolve().parents[2] / "data" / "habitguard.db"

class DatabaseManager:
    def __init__(self):
        DATABASE_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._create_tables()
        self._migrate_jsonl_data()

    def get_connection(self):
        """Open a new connection, configure WAL mode and busy_timeout, and return it."""
        conn = sqlite3.connect(str(DATABASE_FILE))
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for concurrent reads & writes
        conn.execute("PRAGMA journal_mode=WAL")
        # Set busy timeout to 5 seconds so sqlite doesn't throw immediate locked errors
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    @contextmanager
    def connection_context(self):
        """Context manager to ensure sqlite connections are closed immediately after use."""
        conn = self.get_connection()
        try:
            yield conn
        finally:
            conn.close()

    # ── Schema ────────────────────────────────────────────────────────────

    def _create_tables(self):
        with self.connection_context() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS usage_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    date TEXT,
                    server_received_at TEXT,
                    payload TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    date TEXT,
                    minutes REAL,
                    domain_usage_minutes TEXT,
                    recorded_at TEXT,
                    UNIQUE(user_id, date)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    event_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    event_type TEXT,
                    timestamp TEXT,
                    server_received_at TEXT,
                    payload TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS interventions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    date TEXT,
                    intervention_type TEXT,
                    friction_type TEXT,
                    usage_status TEXT,
                    recommended_timer_minutes REAL,
                    server_received_at TEXT,
                    payload TEXT
                )
            """)

            # ── Backward-compatible aliases for the old table names ──
            conn.execute("""
                CREATE VIEW IF NOT EXISTS snapshots AS
                SELECT * FROM usage_snapshots
            """)
            conn.execute("""
                CREATE VIEW IF NOT EXISTS feedback_events AS
                SELECT * FROM feedback
            """)

    # ── JSONL migration (one-time, from legacy flat files) ────────────────

    def _migrate_jsonl_data(self):
        # Migrate usage snapshots
        jsonl_snapshots_file = DATABASE_FILE.parent / "usage_snapshots.jsonl"
        
        has_snapshots = False
        with self.connection_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM usage_snapshots")
            has_snapshots = (cursor.fetchone()[0] > 0)

        if not has_snapshots and jsonl_snapshots_file.exists():
            print(f"Migrating snapshots from {jsonl_snapshots_file} to SQLite...")
            try:
                with self.connection_context() as conn:
                    with open(jsonl_snapshots_file, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                snapshot = json.loads(line)
                                snapshot_id = snapshot.get("snapshot_id")
                                user_id = snapshot.get("user_id", "local_user")
                                date = snapshot.get("date")
                                server_received_at = snapshot.get("server_received_at") or datetime.now(timezone.utc).isoformat()
                                conn.execute(
                                    "INSERT OR IGNORE INTO usage_snapshots (snapshot_id, user_id, date, server_received_at, payload) VALUES (?, ?, ?, ?, ?)",
                                    (snapshot_id, str(user_id), date, server_received_at, json.dumps(snapshot))
                                )
                                conn.commit()
                            except (json.JSONDecodeError, KeyError) as e:
                                print(f"Failed to migrate snapshot line: {e}")
                # Rename the backup file
                jsonl_snapshots_file.rename(jsonl_snapshots_file.with_suffix(".jsonl.bak"))
            except Exception as e:
                print(f"Error during snapshots migration: {e}")

        # Migrate feedback events
        jsonl_feedback_file = DATABASE_FILE.parent / "feedback_events.jsonl"
        
        has_feedback = False
        with self.connection_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM feedback")
            has_feedback = (cursor.fetchone()[0] > 0)

        if not has_feedback and jsonl_feedback_file.exists():
            print(f"Migrating feedback events from {jsonl_feedback_file} to SQLite...")
            try:
                with self.connection_context() as conn:
                    with open(jsonl_feedback_file, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                event = json.loads(line)
                                event_id = event.get("event_id")
                                user_id = event.get("user_id", "local_user")
                                event_type = event.get("event_type", "unknown")
                                timestamp = event.get("timestamp")
                                server_received_at = event.get("server_received_at") or datetime.now(timezone.utc).isoformat()
                                conn.execute(
                                    "INSERT OR IGNORE INTO feedback (event_id, user_id, event_type, timestamp, server_received_at, payload) VALUES (?, ?, ?, ?, ?, ?)",
                                    (event_id, str(user_id), event_type, timestamp, server_received_at, json.dumps(event))
                                )
                                conn.commit()
                            except (json.JSONDecodeError, KeyError) as e:
                                print(f"Failed to migrate feedback line: {e}")
                # Rename the backup file
                jsonl_feedback_file.rename(jsonl_feedback_file.with_suffix(".jsonl.bak"))
            except Exception as e:
                print(f"Error during feedback migration: {e}")

    # ── Usage Snapshots ───────────────────────────────────────────────────

    def save_usage_snapshot(self, snapshot_id: str, user_id: str, date: str, server_received_at: str, payload: dict):
        """Save a usage snapshot to the usage_snapshots table."""
        with self.connection_context() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO usage_snapshots (snapshot_id, user_id, date, server_received_at, payload) VALUES (?, ?, ?, ?, ?)",
                (snapshot_id, str(user_id), date, server_received_at, json.dumps(payload))
            )
            conn.commit()

    def get_usage_snapshots(self, user_id=None) -> list:
        """Retrieve usage snapshots, optionally filtered by user_id."""
        with self.connection_context() as conn:
            cursor = conn.cursor()
            if user_id is not None:
                cursor.execute("SELECT payload FROM usage_snapshots WHERE user_id = ? ORDER BY server_received_at ASC", (str(user_id),))
            else:
                cursor.execute("SELECT payload FROM usage_snapshots ORDER BY server_received_at ASC")

            rows = cursor.fetchall()
            snapshots = []
            for row in rows:
                try:
                    snapshots.append(json.loads(row["payload"]))
                except json.JSONDecodeError:
                    continue
            return snapshots

    # Backward-compatible aliases (used by usage_service.py / feedback_service.py)
    def save_snapshot(self, snapshot_id: str, user_id: str, date: str, server_received_at: str, payload: dict):
        """Alias for save_usage_snapshot — keeps existing callers working."""
        return self.save_usage_snapshot(snapshot_id, user_id, date, server_received_at, payload)

    def load_snapshots(self, user_id=None) -> list:
        """Alias for get_usage_snapshots — keeps existing callers working."""
        return self.get_usage_snapshots(user_id=user_id)

    # ── Daily Usage ───────────────────────────────────────────────────────

    def save_daily_usage(self, user_id: str, date: str, minutes: float, domain_usage_minutes: dict = None):
        """Upsert a daily usage record for a user/date pair."""
        recorded_at = datetime.now(timezone.utc).isoformat()
        domain_json = json.dumps(domain_usage_minutes) if domain_usage_minutes else None
        with self.connection_context() as conn:
            conn.execute(
                """INSERT INTO daily_usage (user_id, date, minutes, domain_usage_minutes, recorded_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(user_id, date)
                   DO UPDATE SET minutes = excluded.minutes,
                                 domain_usage_minutes = excluded.domain_usage_minutes,
                                 recorded_at = excluded.recorded_at""",
                (str(user_id), date, minutes, domain_json, recorded_at)
            )
            conn.commit()

    def get_daily_usage_history(self, user_id: str = "local_user") -> list:
        """Return daily usage rows for a user, sorted by date ascending."""
        with self.connection_context() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT date, minutes, domain_usage_minutes FROM daily_usage WHERE user_id = ? ORDER BY date ASC",
                (str(user_id),)
            )
            rows = cursor.fetchall()
            history = []
            for row in rows:
                entry = {"date": row["date"], "minutes": row["minutes"]}
                if row["domain_usage_minutes"]:
                    try:
                        entry["domain_usage_minutes"] = json.loads(row["domain_usage_minutes"])
                    except json.JSONDecodeError:
                        entry["domain_usage_minutes"] = {}
                history.append(entry)
            return history

    # ── Feedback ──────────────────────────────────────────────────────────

    def save_feedback(self, event_id: str, user_id: str, event_type: str, timestamp: str, server_received_at: str, payload: dict):
        """Save a feedback event to the feedback table."""
        with self.connection_context() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO feedback (event_id, user_id, event_type, timestamp, server_received_at, payload) VALUES (?, ?, ?, ?, ?, ?)",
                (event_id, str(user_id), event_type, timestamp, server_received_at, json.dumps(payload))
            )
            conn.commit()

    def get_feedback(self) -> list:
        """Retrieve all feedback events, sorted by server_received_at ascending."""
        with self.connection_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT payload FROM feedback ORDER BY server_received_at ASC")
            rows = cursor.fetchall()
            events = []
            for row in rows:
                try:
                    events.append(json.loads(row["payload"]))
                except json.JSONDecodeError:
                    continue
            return events

    # Backward-compatible aliases (used by feedback_service.py)
    def save_feedback_event(self, event_id: str, user_id: str, event_type: str, timestamp: str, server_received_at: str, payload: dict):
        """Alias for save_feedback — keeps existing callers working."""
        return self.save_feedback(event_id, user_id, event_type, timestamp, server_received_at, payload)

    def load_feedback_events(self) -> list:
        """Alias for get_feedback — keeps existing callers working."""
        return self.get_feedback()

    # ── Interventions ─────────────────────────────────────────────────────

    def save_intervention(self, user_id: str, date: str, payload: dict):
        """Save an intervention decision record."""
        server_received_at = datetime.now(timezone.utc).isoformat()
        intervention_type = payload.get("intervention_type")
        friction_type = payload.get("friction_type")
        usage_status = payload.get("usage_status")
        recommended_timer = payload.get("recommended_timer_minutes")
        with self.connection_context() as conn:
            conn.execute(
                """INSERT INTO interventions
                   (user_id, date, intervention_type, friction_type, usage_status,
                    recommended_timer_minutes, server_received_at, payload)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (str(user_id), date, intervention_type, friction_type, usage_status,
                 recommended_timer, server_received_at, json.dumps(payload))
            )
            conn.commit()

    def get_interventions(self, user_id: str = "local_user") -> list:
        """Retrieve intervention records for a user, sorted by received time ascending."""
        with self.connection_context() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT payload FROM interventions WHERE user_id = ? ORDER BY server_received_at ASC",
                (str(user_id),)
            )
            rows = cursor.fetchall()
            interventions = []
            for row in rows:
                try:
                    interventions.append(json.loads(row["payload"]))
                except json.JSONDecodeError:
                    continue
            return interventions

db_manager = DatabaseManager()
