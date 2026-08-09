from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from app.db.connection import get_db_connection

VALID_ACTIONS = {
    "finish", "extend_5", "task_not_finished", "dismiss", "stop_reminders",
    "change_plan", "no_timer", "overlay_dismissed", "overlay_dismissed_by_user",
    "break_accepted", "break_completed", "break_skipped"
}

# Accepted string values for task_completion and time_sufficient
VALID_TASK_COMPLETION = {"completed", "partly_completed", "not_completed", "unknown"}
VALID_TIME_SUFFICIENT = {"sufficient", "partly_sufficient", "insufficient", "unknown"}

class FeedbackRepository:
    def add_feedback_event(
        self,
        session_id: str,
        user_id: str,
        action: str,
        task_completion: Optional[str] = None,
        time_sufficient: Optional[str] = None
    ) -> Dict[str, Any]:
        # Normalise: accept None or unknown for unrecognised values
        if task_completion not in VALID_TASK_COMPLETION:
            task_completion = None
        if time_sufficient not in VALID_TIME_SUFFICIENT:
            time_sufficient = None
        if action not in VALID_ACTIONS:
            action = "dismiss"
            
        now_utc = datetime.now(timezone.utc).isoformat()
        conn = get_db_connection()
        try:
            with conn:
                cur = conn.cursor()
                
                # Ensure session stub exists to satisfy foreign key constraint if needed
                cur.execute("SELECT session_id FROM technical_sessions WHERE session_id = ?", (session_id,))
                if not cur.fetchone():
                    conn.execute(
                        "INSERT INTO technical_sessions (session_id, user_id, domain, started_at_utc, status, created_at_utc, updated_at_utc) VALUES (?, ?, 'legacy', ?, 'ended', ?, ?)",
                        (session_id, user_id, now_utc, now_utc, now_utc)
                    )

                cur.execute(
                    """INSERT INTO feedback_events
                       (session_id, user_id, action, task_completion, time_sufficient, created_at_utc)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (session_id, user_id, action, task_completion, time_sufficient, now_utc)
                )
                event_id = cur.lastrowid
            return {
                "id": event_id,
                "session_id": session_id,
                "user_id": user_id,
                "action": action,
                "task_completion": task_completion,
                "time_sufficient": time_sufficient,
                "created_at_utc": now_utc
            }
        finally:
            conn.close()

    def get_user_feedback_summary(self, user_id: str) -> Dict[str, Any]:
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT action, COUNT(*) as count FROM feedback_events WHERE user_id = ? GROUP BY action", (user_id,))
            counts = {row["action"]: row["count"] for row in cur.fetchall()}
            
            total = sum(counts.values())
            dismiss_count = counts.get("dismiss", 0) + counts.get("overlay_dismissed", 0)
            accept_count = counts.get("finish", 0) + counts.get("extend_5", 0) + counts.get("break_accepted", 0)
            
            return {
                "total_events": total,
                "finish_count": counts.get("finish", 0),
                "extend_count": counts.get("extend_5", 0),
                "dismiss_count": dismiss_count,
                "task_not_finished_count": counts.get("task_not_finished", 0),
                "stop_reminders_count": counts.get("stop_reminders", 0),
                "acceptance_rate": (accept_count) / (total + 1e-5) if total > 0 else 0.5
            }
        finally:
            conn.close()

    def get_most_dismissed_sites(self, user_id: str, limit: int = 5) -> List[tuple]:
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """SELECT ts.domain, COUNT(*) as count 
                   FROM feedback_events fe 
                   JOIN technical_sessions ts ON fe.session_id = ts.session_id 
                   WHERE fe.user_id = ? AND fe.action IN ('dismiss', 'overlay_dismissed', 'overlay_dismissed_by_user') 
                   GROUP BY ts.domain 
                   ORDER BY count DESC 
                   LIMIT ?""",
                (user_id, limit)
            )
            return [(row["domain"], row["count"]) for row in cur.fetchall()]
        finally:
            conn.close()

