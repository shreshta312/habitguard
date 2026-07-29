import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from app.db.connection import get_db_connection

class DeliveryTracesRepository:
    def record_trace(
        self,
        decision_id: str,
        session_id: str,
        user_id: str,
        domain: str,
        delivery_status: str,
        channel: str = "none",
        requested_channel: Optional[str] = "notification",
        fallback_channel: Optional[str] = None,
        intervention_preserved: bool = False,
        should_notify: bool = False,
        should_overlay: bool = False,
        eligible: bool = False,
        attempted_at_utc: Optional[str] = None,
        chrome_notification_id: Optional[str] = None,
        failure_reason: Optional[str] = None,
        episode_id: Optional[str] = None,
        cooldown_source: Optional[str] = "VERSIONED_DEFAULT",
        next_eligible_at: Optional[str] = None
    ) -> Dict[str, Any]:
        trace_id = f"trc_{uuid.uuid4().hex[:12]}"
        now_utc = datetime.now(timezone.utc).isoformat()
        attempted_time = attempted_at_utc or now_utc

        conn = get_db_connection()
        try:
            with conn:
                conn.execute(
                    """INSERT INTO delivery_traces
                       (trace_id, decision_id, session_id, episode_id, user_id, domain, channel, requested_channel, fallback_channel, intervention_preserved, should_notify, should_overlay, eligible, attempted_at_utc, delivery_status, chrome_notification_id, failure_reason, cooldown_source, next_eligible_at, created_at_utc)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        trace_id, decision_id, session_id, episode_id, user_id, domain, channel,
                        requested_channel or "notification", fallback_channel, 1 if intervention_preserved else 0,
                        1 if should_notify else 0, 1 if should_overlay else 0, 1 if eligible else 0,
                        attempted_time, delivery_status, chrome_notification_id, failure_reason,
                        cooldown_source or "VERSIONED_DEFAULT", next_eligible_at, now_utc
                    )
                )
            return self.get_trace(trace_id)
        finally:
            conn.close()

    def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM delivery_traces WHERE trace_id = ?", (trace_id,))
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_session_traces(self, session_id: str) -> List[Dict[str, Any]]:
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM delivery_traces WHERE session_id = ? ORDER BY created_at_utc DESC", (session_id,))
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()
