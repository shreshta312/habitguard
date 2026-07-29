from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from app.db.connection import get_db_connection

class PersonalParametersRepository:
    def get_parameter(self, user_id: str, parameter_name: str, context_key: str = "global") -> Optional[Dict[str, Any]]:
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM personal_parameters WHERE user_id = ? AND parameter_name = ? AND context_key = ?",
                (user_id, parameter_name, context_key)
            )
            row = cur.fetchone()
            if not row:
                return None
            return dict(row)
        finally:
            conn.close()

    def set_parameter(
        self,
        user_id: str,
        parameter_name: str,
        value: float,
        source: str,
        context_key: str = "global",
        confidence: float = 0.5,
        sample_count: int = 1,
        version: str = "2.0.0"
    ) -> Dict[str, Any]:
        now_utc = datetime.now(timezone.utc).isoformat()
        conn = get_db_connection()
        try:
            with conn:
                conn.execute(
                    """INSERT INTO personal_parameters
                       (user_id, parameter_name, context_key, value, source, confidence, sample_count, version, updated_at_utc)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(user_id, parameter_name, context_key) DO UPDATE SET
                           value = excluded.value,
                           source = excluded.source,
                           confidence = excluded.confidence,
                           sample_count = excluded.sample_count,
                           version = excluded.version,
                           updated_at_utc = excluded.updated_at_utc""",
                    (user_id, parameter_name, context_key, value, source, confidence, sample_count, version, now_utc)
                )
            return self.get_parameter(user_id, parameter_name, context_key)
        finally:
            conn.close()

    def get_all_user_parameters(self, user_id: str) -> List[Dict[str, Any]]:
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM personal_parameters WHERE user_id = ?", (user_id,))
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()
