import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from app.db.connection import get_db_connection

class GoalsRepository:
    def get_goal(self, user_id: str) -> Optional[Dict[str, Any]]:
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT user_id, selected_domains_json, reduction_intensity, target_reduction_percent, status, created_at_utc, updated_at_utc FROM user_goals WHERE user_id = ?",
                (user_id,)
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "user_id": row["user_id"],
                "selected_domains": json.loads(row["selected_domains_json"]),
                "reduction_intensity": row["reduction_intensity"],
                "target_reduction_percent": row["target_reduction_percent"],
                "status": row["status"],
                "created_at_utc": row["created_at_utc"],
                "updated_at_utc": row["updated_at_utc"]
            }
        finally:
            conn.close()

    def upsert_goal(self, user_id: str, selected_domains: list[str], reduction_intensity: str = "moderate", target_reduction_percent: float = 20.0) -> Dict[str, Any]:
        conn = get_db_connection()
        now_utc = datetime.now(timezone.utc).isoformat()
        domains_json = json.dumps(selected_domains)
        try:
            with conn:
                conn.execute(
                    """INSERT INTO user_goals (user_id, selected_domains_json, reduction_intensity, target_reduction_percent, status, created_at_utc, updated_at_utc)
                       VALUES (?, ?, ?, ?, 'active', ?, ?)
                       ON CONFLICT(user_id) DO UPDATE SET
                           selected_domains_json = excluded.selected_domains_json,
                           reduction_intensity = excluded.reduction_intensity,
                           target_reduction_percent = excluded.target_reduction_percent,
                           updated_at_utc = excluded.updated_at_utc""",
                    (user_id, domains_json, reduction_intensity, target_reduction_percent, now_utc, now_utc)
                )
            return self.get_goal(user_id)
        finally:
            conn.close()
