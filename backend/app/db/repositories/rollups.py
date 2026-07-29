from typing import Optional, Dict, Any, List
from app.db.connection import get_db_connection

class DailyUsageRollupsRepository:
    def upsert_rollup(
        self,
        user_id: str,
        local_date: str,
        domain: str,
        focused_minutes: float = 0.0,
        planned_minutes: float = 0.0,
        unplanned_minutes: float = 0.0,
        unknown_minutes: float = 0.0,
        necessary_minutes: float = 0.0,
        reopen_count: int = 0,
        longest_uninterrupted_minutes: float = 0.0,
        cross_domain_switches: int = 0
    ) -> Dict[str, Any]:
        conn = get_db_connection()
        try:
            with conn:
                conn.execute(
                    """INSERT INTO daily_usage_rollups
                       (user_id, local_date, domain, focused_minutes, planned_minutes, unplanned_minutes,
                        unknown_minutes, necessary_minutes, reopen_count, longest_uninterrupted_minutes, cross_domain_switches)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(user_id, local_date, domain) DO UPDATE SET
                           focused_minutes = daily_usage_rollups.focused_minutes + excluded.focused_minutes,
                           planned_minutes = daily_usage_rollups.planned_minutes + excluded.planned_minutes,
                           unplanned_minutes = daily_usage_rollups.unplanned_minutes + excluded.unplanned_minutes,
                           unknown_minutes = daily_usage_rollups.unknown_minutes + excluded.unknown_minutes,
                           necessary_minutes = daily_usage_rollups.necessary_minutes + excluded.necessary_minutes,
                           reopen_count = daily_usage_rollups.reopen_count + excluded.reopen_count,
                           longest_uninterrupted_minutes = MAX(daily_usage_rollups.longest_uninterrupted_minutes, excluded.longest_uninterrupted_minutes),
                           cross_domain_switches = daily_usage_rollups.cross_domain_switches + excluded.cross_domain_switches""",
                    (
                        user_id, local_date, domain, focused_minutes, planned_minutes, unplanned_minutes,
                        unknown_minutes, necessary_minutes, reopen_count, longest_uninterrupted_minutes, cross_domain_switches
                    )
                )
            cur = conn.cursor()
            cur.execute("SELECT * FROM daily_usage_rollups WHERE user_id = ? AND local_date = ? AND domain = ?", (user_id, local_date, domain))
            return dict(cur.fetchone())
        finally:
            conn.close()

    def record_activity_interval(
        self,
        user_id: str,
        domain: str,
        end_timestamp_utc: str,
        duration_ms: float,
        classification: str = "unknown",
        local_timezone: str = "UTC"
    ):
        from datetime import datetime, timezone, timedelta
        import zoneinfo

        try:
            end_dt = datetime.fromisoformat(end_timestamp_utc.replace("Z", "+00:00"))
        except Exception:
            end_dt = datetime.now(timezone.utc)

        duration_sec = duration_ms / 1000.0
        start_dt = end_dt - timedelta(seconds=duration_sec)

        try:
            tz = zoneinfo.ZoneInfo(local_timezone)
        except Exception:
            tz = timezone.utc

        start_local = start_dt.astimezone(tz)
        end_local = end_dt.astimezone(tz)

        start_date_str = start_local.strftime("%Y-%m-%d")
        end_date_str = end_local.strftime("%Y-%m-%d")

        if start_date_str == end_date_str:
            focused_mins = round(duration_ms / 60000.0, 4)
            necessary_mins = focused_mins if classification in {"work_study", "necessary"} else 0.0
            unknown_mins = focused_mins if classification == "unknown" else 0.0
            self.upsert_rollup(
                user_id=user_id,
                local_date=start_date_str,
                domain=domain,
                focused_minutes=focused_mins,
                necessary_minutes=necessary_mins,
                unknown_minutes=unknown_mins
            )
        else:
            midnight_local = (start_local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            pre_midnight_sec = (midnight_local - start_local).total_seconds()
            post_midnight_sec = max(0.0, duration_sec - pre_midnight_sec)

            pre_mins = round(pre_midnight_sec / 60.0, 4)
            post_mins = round(post_midnight_sec / 60.0, 4)

            self.upsert_rollup(
                user_id=user_id,
                local_date=start_date_str,
                domain=domain,
                focused_minutes=pre_mins,
                necessary_minutes=pre_mins if classification in {"work_study", "necessary"} else 0.0,
                unknown_minutes=pre_mins if classification == "unknown" else 0.0
            )

            self.upsert_rollup(
                user_id=user_id,
                local_date=end_date_str,
                domain=domain,
                focused_minutes=post_mins,
                necessary_minutes=post_mins if classification in {"work_study", "necessary"} else 0.0,
                unknown_minutes=post_mins if classification == "unknown" else 0.0
            )

    def get_user_rollups(self, user_id: str, days: int = 7) -> List[Dict[str, Any]]:
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM daily_usage_rollups WHERE user_id = ? ORDER BY local_date DESC LIMIT ?",
                (user_id, days * 10)
            )
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()
