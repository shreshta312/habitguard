from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from app.db.repositories.sessions import SessionsRepository

# Validation parameters
CLOCK_SKEW_TOLERANCE = timedelta(minutes=5)
MAX_EVENT_DURATION_MS = 3600000  # 1 hour max per event

class FocusedUsageTracker:
    """
    Validates, deduplicates, reconstructs and aggregates focused browser time from activity records.
    Computes tracking reliability score.
    """
    def __init__(self, sessions_repo: Optional[SessionsRepository] = None):
        self.repo = sessions_repo or SessionsRepository()

    def process_activities(self, session_id: str, user_id: str, domain: str, activities: List[Dict[str, Any]]) -> Dict[str, Any]:
        session = self.repo.get_technical_session(session_id)
        now_utc = datetime.now(timezone.utc)

        session_start_utc = None
        if session and session.get("started_at_utc"):
            try:
                session_start_utc = datetime.fromisoformat(str(session["started_at_utc"]))
                if session_start_utc.tzinfo is None:
                    session_start_utc = session_start_utc.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                session_start_utc = None

        valid_activities = []
        rejected_count = 0

        for act in activities:
            duration_ms = act.get("focused_duration_ms")
            if duration_ms is None or duration_ms <= 0 or duration_ms > MAX_EVENT_DURATION_MS:
                rejected_count += 1
                continue

            ts_str = act.get("event_timestamp_utc")
            if ts_str:
                try:
                    event_ts = datetime.fromisoformat(str(ts_str))
                    if event_ts.tzinfo is None:
                        event_ts = event_ts.replace(tzinfo=timezone.utc)

                    # Reject if event predates session start beyond clock skew tolerance
                    if session_start_utc and event_ts < (session_start_utc - CLOCK_SKEW_TOLERANCE):
                        rejected_count += 1
                        continue

                    # Reject if event is implausibly in the future
                    if event_ts > (now_utc + CLOCK_SKEW_TOLERANCE):
                        rejected_count += 1
                        continue
                except (ValueError, TypeError):
                    pass

            valid_activities.append(act)

        added = self.repo.add_activity_batch(session_id, user_id, domain, valid_activities)
        inserted_activities = getattr(self.repo, "last_inserted_activities", valid_activities if added > 0 else [])

        total_focused_minutes = self.calculate_focused_minutes(session_id)
        reliability = self.calculate_tracking_reliability(valid_activities)

        return {
            "session_id": session_id,
            "events_received": len(activities),
            "events_added": added,
            "events_rejected": rejected_count,
            "inserted_activities": inserted_activities,
            "total_focused_minutes": total_focused_minutes,
            "tracking_reliability": reliability
        }

    def calculate_focused_minutes(self, session_id: str) -> float:
        session = self.repo.get_technical_session(session_id)
        if not session:
            return 0.0

        conn = self.repo.get_db_connection() if hasattr(self.repo, "get_db_connection") else None
        if not conn:
            from app.db.connection import get_db_connection
            conn = get_db_connection()

        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT SUM(focused_duration_ms) FROM session_activities WHERE session_id = ?",
                (session_id,)
            )
            row = cur.fetchone()
            total_ms = row[0] if row and row[0] is not None else 0
            return round(total_ms / 60000.0, 2)
        finally:
            conn.close()

    def calculate_tracking_reliability(self, activities: List[Dict[str, Any]]) -> float:
        if not activities:
            return 1.0
        valid_count = sum(1 for a in activities if a.get("client_event_id") and a.get("event_timestamp_utc"))
        return round(valid_count / float(len(activities)), 2)
