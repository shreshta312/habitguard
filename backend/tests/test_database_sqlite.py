"""
test_database_sqlite.py

Tests for the SQLite-backed DatabaseManager.
Uses an in-memory SQLite database to avoid touching real data.
"""
import json
import sqlite3
import pytest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, timezone


# ── Helpers: patch DATABASE_FILE so we use ":memory:" ─────────────────────────

@pytest.fixture
def db_manager():
    """Create a fresh DatabaseManager backed by in-memory SQLite."""
    # Patch the module-level constant before importing
    import importlib
    import app.services.database as db_module

    # Save original
    original_db_file = db_module.DATABASE_FILE

    # Use a temp file instead of :memory: because DatabaseManager
    # does Path operations (mkdir etc.) on the parent.
    import tempfile, os
    tmpdir = tempfile.mkdtemp()
    tmp_db = Path(tmpdir) / "test.db"
    db_module.DATABASE_FILE = tmp_db

    # Re-create the manager with the patched path
    manager = db_module.DatabaseManager()
    yield manager

    # Cleanup
    if tmp_db.exists():
        os.remove(tmp_db)
    os.rmdir(tmpdir)
    db_module.DATABASE_FILE = original_db_file


# ── Usage Snapshots ───────────────────────────────────────────────────────────

class TestUsageSnapshots:
    def test_save_and_get_snapshot(self, db_manager):
        payload = {"screen_time_min": 45, "domains": {"youtube.com": 30}}
        db_manager.save_usage_snapshot(
            snapshot_id="snap-001",
            user_id="user_1",
            date="2025-07-01",
            server_received_at="2025-07-01T10:00:00Z",
            payload=payload,
        )

        results = db_manager.get_usage_snapshots(user_id="user_1")
        assert len(results) == 1
        assert results[0]["screen_time_min"] == 45

    def test_get_snapshots_empty(self, db_manager):
        results = db_manager.get_usage_snapshots(user_id="nonexistent")
        assert results == []

    def test_save_snapshot_upsert(self, db_manager):
        """INSERT OR REPLACE should update an existing snapshot."""
        db_manager.save_usage_snapshot("snap-002", "user_1", "2025-07-01", "2025-07-01T10:00:00Z", {"v": 1})
        db_manager.save_usage_snapshot("snap-002", "user_1", "2025-07-01", "2025-07-01T11:00:00Z", {"v": 2})

        results = db_manager.get_usage_snapshots(user_id="user_1")
        assert len(results) == 1
        assert results[0]["v"] == 2

    def test_save_snapshot_alias(self, db_manager):
        """save_snapshot should be an alias for save_usage_snapshot."""
        db_manager.save_snapshot("snap-a", "u", "2025-01-01", "2025-01-01T00:00:00Z", {"alias": True})
        results = db_manager.load_snapshots(user_id="u")
        assert len(results) == 1
        assert results[0]["alias"] is True

    def test_get_all_snapshots_no_filter(self, db_manager):
        db_manager.save_usage_snapshot("s1", "a", "2025-01-01", "2025-01-01T00:00:00Z", {"u": "a"})
        db_manager.save_usage_snapshot("s2", "b", "2025-01-01", "2025-01-01T00:01:00Z", {"u": "b"})

        results = db_manager.get_usage_snapshots()
        assert len(results) == 2


# ── Daily Usage ───────────────────────────────────────────────────────────────

class TestDailyUsage:
    def test_save_and_get_daily_usage(self, db_manager):
        db_manager.save_daily_usage("user_1", "2025-07-01", 120.5, {"youtube.com": 80})
        history = db_manager.get_daily_usage_history("user_1")
        assert len(history) == 1
        assert history[0]["date"] == "2025-07-01"
        assert history[0]["minutes"] == 120.5
        assert history[0]["domain_usage_minutes"]["youtube.com"] == 80

    def test_upsert_daily_usage(self, db_manager):
        """Same user/date should update, not duplicate."""
        db_manager.save_daily_usage("user_1", "2025-07-01", 60)
        db_manager.save_daily_usage("user_1", "2025-07-01", 120)

        history = db_manager.get_daily_usage_history("user_1")
        assert len(history) == 1
        assert history[0]["minutes"] == 120

    def test_daily_usage_ordering(self, db_manager):
        db_manager.save_daily_usage("u", "2025-07-03", 30)
        db_manager.save_daily_usage("u", "2025-07-01", 10)
        db_manager.save_daily_usage("u", "2025-07-02", 20)

        history = db_manager.get_daily_usage_history("u")
        dates = [h["date"] for h in history]
        assert dates == ["2025-07-01", "2025-07-02", "2025-07-03"]

    def test_daily_usage_without_domains(self, db_manager):
        db_manager.save_daily_usage("u", "2025-07-01", 60)
        history = db_manager.get_daily_usage_history("u")
        assert "domain_usage_minutes" not in history[0]


# ── Feedback ──────────────────────────────────────────────────────────────────

class TestFeedback:
    def test_save_and_get_feedback(self, db_manager):
        payload = {"event_type": "dismiss", "reason": "not_helpful"}
        db_manager.save_feedback(
            event_id="evt-001",
            user_id="user_1",
            event_type="dismiss",
            timestamp="2025-07-01T10:00:00Z",
            server_received_at="2025-07-01T10:00:01Z",
            payload=payload,
        )

        events = db_manager.get_feedback()
        assert len(events) == 1
        assert events[0]["event_type"] == "dismiss"

    def test_feedback_alias(self, db_manager):
        db_manager.save_feedback_event("e1", "u", "click", "2025-01-01T00:00:00Z", "2025-01-01T00:00:01Z", {"t": "click"})
        events = db_manager.load_feedback_events()
        assert len(events) == 1
        assert events[0]["t"] == "click"

    def test_feedback_upsert(self, db_manager):
        db_manager.save_feedback("e1", "u", "a", "t1", "s1", {"v": 1})
        db_manager.save_feedback("e1", "u", "b", "t2", "s2", {"v": 2})

        events = db_manager.get_feedback()
        assert len(events) == 1
        assert events[0]["v"] == 2


# ── Interventions ─────────────────────────────────────────────────────────────

class TestInterventions:
    def test_save_and_get_intervention(self, db_manager):
        payload = {
            "intervention_type": "notification",
            "friction_type": "WARNING_TIMER",
            "usage_status": "OVERUSE",
            "recommended_timer_minutes": 15,
            "message": "Take a break!",
        }
        db_manager.save_intervention("user_1", "2025-07-01", payload)

        results = db_manager.get_interventions("user_1")
        assert len(results) == 1
        assert results[0]["usage_status"] == "OVERUSE"
        assert results[0]["recommended_timer_minutes"] == 15

    def test_multiple_interventions_same_day(self, db_manager):
        """Unlike daily_usage, interventions can have multiple per day."""
        db_manager.save_intervention("u", "2025-07-01", {"usage_status": "NORMAL"})
        db_manager.save_intervention("u", "2025-07-01", {"usage_status": "OVERUSE"})

        results = db_manager.get_interventions("u")
        assert len(results) == 2

    def test_interventions_empty(self, db_manager):
        results = db_manager.get_interventions("nobody")
        assert results == []


# ── Table existence ───────────────────────────────────────────────────────────

class TestSchemaCreation:
    def test_tables_exist(self, db_manager):
        with db_manager.connection_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall()]
        assert "usage_snapshots" in tables
        assert "daily_usage" in tables
        assert "feedback" in tables
        assert "interventions" in tables

    def test_views_exist(self, db_manager):
        with db_manager.connection_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='view' ORDER BY name")
            views = [row[0] for row in cursor.fetchall()]
        assert "snapshots" in views
        assert "feedback_events" in views
