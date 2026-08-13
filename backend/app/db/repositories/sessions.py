import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from app.db.connection import get_db_connection

VALID_PURPOSES = {"work_study", "necessary", "entertainment", "habitual_browsing", "unknown"}
VALID_TIMER_MODES = {"planned", "no_timer"}

class SessionsRepository:
    def create_intent_episode(
        self,
        user_id: str,
        domain: str,
        purpose: str,
        intended_minutes: Optional[float] = None,
        timer_mode: str = "planned",
        remember_today: bool = False
    ) -> Dict[str, Any]:
        if purpose == "no_timer" or purpose not in VALID_PURPOSES:
            purpose = "unknown"
            timer_mode = "no_timer"
            intended_minutes = None
        if timer_mode not in VALID_TIMER_MODES:
            timer_mode = "planned"

        episode_id = f"ep_{uuid.uuid4().hex[:12]}"
        now_utc = datetime.now(timezone.utc).isoformat()
        orig_minutes = intended_minutes if intended_minutes is not None else None

        conn = get_db_connection()
        try:
            with conn:
                conn.execute(
                    """INSERT INTO intent_episodes
                       (episode_id, user_id, domain, purpose, intended_minutes, original_intended_minutes, extension_minutes, timer_mode, remember_today, started_at_utc, last_activity_at_utc, last_focused_at_utc, status, created_at_utc, updated_at_utc)
                       VALUES (?, ?, ?, ?, ?, ?, 0.0, ?, ?, ?, ?, ?, 'active', ?, ?)""",
                    (episode_id, user_id, domain, purpose, intended_minutes, orig_minutes, timer_mode, 1 if remember_today else 0, now_utc, now_utc, now_utc, now_utc, now_utc)
                )
            return self.get_intent_episode(episode_id)
        finally:
            conn.close()

    def get_active_intent_episode(self, user_id: str, domain: str) -> Optional[Dict[str, Any]]:
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM intent_episodes WHERE user_id = ? AND domain = ? AND status = 'active' ORDER BY created_at_utc DESC LIMIT 1",
                (user_id, domain)
            )
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def resolve_intent_episode(
        self,
        user_id: str,
        domain: str,
        purpose: Optional[str] = "unknown",
        intended_minutes: Optional[float] = None,
        timer_mode: str = "planned",
        remember_today: bool = False,
        now_iso: Optional[str] = None
    ) -> Dict[str, Any]:
        from app.core.config import SESSION_RESUME_GAP_MINUTES
        if now_iso:
            try:
                now_dt = datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
                if now_dt.tzinfo is None:
                    now_dt = now_dt.replace(tzinfo=timezone.utc)
            except Exception:
                now_dt = datetime.now(timezone.utc)
            now_utc = now_iso
        else:
            now_dt = datetime.now(timezone.utc)
            now_utc = now_dt.isoformat()

        active_ep = self.get_active_intent_episode(user_id, domain)
        if active_ep:
            unfocused_str = active_ep.get("unfocused_at_utc") or active_ep.get("last_focused_at_utc") or active_ep.get("last_activity_at_utc") or active_ep.get("started_at_utc")
            try:
                unfocused_dt = datetime.fromisoformat(unfocused_str.replace("Z", "+00:00"))
                if unfocused_dt.tzinfo is None:
                    unfocused_dt = unfocused_dt.replace(tzinfo=timezone.utc)
                gap_minutes = (now_dt - unfocused_dt).total_seconds() / 60.0
            except Exception:
                gap_minutes = 999.0

            # Check if user explicitly provided a DIFFERENT non-default purpose/intended_minutes
            is_explicit_new_plan = (purpose is not None and purpose not in (None, "unknown") and purpose != active_ep.get("purpose")) or \
                                  (intended_minutes is not None and intended_minutes != active_ep.get("intended_minutes"))

            if gap_minutes <= SESSION_RESUME_GAP_MINUTES and active_ep.get("status") == "active" and not is_explicit_new_plan:
                # Restore active episode
                conn = get_db_connection()
                try:
                    with conn:
                        conn.execute(
                            "UPDATE intent_episodes SET last_activity_at_utc = ?, last_focused_at_utc = ?, unfocused_at_utc = NULL, updated_at_utc = ? WHERE episode_id = ?",
                            (now_utc, now_utc, now_utc, active_ep["episode_id"])
                        )
                    return self.get_intent_episode(active_ep["episode_id"])
                finally:
                    conn.close()
            else:
                # Expire old episode with gap_timeout
                conn = get_db_connection()
                try:
                    with conn:
                        conn.execute(
                            "UPDATE intent_episodes SET status = 'expired', expiry_reason = 'gap_timeout', ended_at_utc = ?, updated_at_utc = ? WHERE episode_id = ?",
                            (now_utc, now_utc, active_ep["episode_id"])
                        )
                finally:
                    conn.close()

        # If starting fresh after gap > 5 min or expired episode, default to NO_PLAN if purpose was unknown
        fresh_purpose = purpose if (purpose and purpose != "unknown") else "unknown"
        fresh_timer_mode = timer_mode if (purpose and purpose != "unknown") else "no_timer"
        fresh_intended = intended_minutes if (purpose and purpose != "unknown") else None

        return self.create_intent_episode(
            user_id=user_id,
            domain=domain,
            purpose=fresh_purpose,
            intended_minutes=fresh_intended,
            timer_mode=fresh_timer_mode,
            remember_today=remember_today
        )

    def end_intent_episode_for_session(self, session_id: str, reason: str = "finished"):
        session = self.get_technical_session(session_id)
        if not session or not session.get("episode_id"):
            return
        now_utc = datetime.now(timezone.utc).isoformat()
        conn = get_db_connection()
        try:
            with conn:
                conn.execute(
                    "UPDATE intent_episodes SET status = 'ended', expiry_reason = ?, ended_at_utc = ?, updated_at_utc = ? WHERE episode_id = ?",
                    (reason, now_utc, now_utc, session["episode_id"])
                )
        finally:
            conn.close()

    def set_unfocused_timestamp(self, session_id: str, timestamp_utc: Optional[str] = None):
        session = self.get_technical_session(session_id)
        if not session or not session.get("episode_id"):
            return
        now_utc = timestamp_utc or datetime.now(timezone.utc).isoformat()
        conn = get_db_connection()
        try:
            with conn:
                conn.execute(
                    "UPDATE intent_episodes SET unfocused_at_utc = ?, updated_at_utc = ? WHERE episode_id = ?",
                    (now_utc, now_utc, session["episode_id"])
                )
        finally:
            conn.close()

    def set_stop_reminders_for_session(self, session_id: str):
        session = self.get_technical_session(session_id)
        if not session or not session.get("episode_id"):
            return
        now_utc = datetime.now(timezone.utc).isoformat()
        conn = get_db_connection()
        try:
            with conn:
                conn.execute(
                    "UPDATE intent_episodes SET stop_reminders = 1, updated_at_utc = ? WHERE episode_id = ?",
                    (now_utc, session["episode_id"])
                )
        finally:
            conn.close()

    def get_episode_focused_minutes(self, episode_id: str) -> float:
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """SELECT SUM(sa.focused_duration_ms)
                   FROM session_activities sa
                   JOIN technical_sessions ts ON sa.session_id = ts.session_id
                   WHERE ts.episode_id = ?""",
                (episode_id,)
            )
            row = cur.fetchone()
            if row and row[0] is not None:
                return round(float(row[0]) / 60000.0, 2)
            return 0.0
        finally:
            conn.close()

    def get_intent_episode(self, episode_id: str) -> Optional[Dict[str, Any]]:
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM intent_episodes WHERE episode_id = ?", (episode_id,))
            row = cur.fetchone()
            if not row:
                return None
            ep = dict(row)
            orig_m = ep.get("original_intended_minutes")
            ext_m = float(ep.get("extension_minutes") or 0.0)
            if orig_m is not None and ep.get("timer_mode") != "no_timer":
                ep["effective_planned_minutes"] = float(orig_m) + ext_m
            else:
                ep["effective_planned_minutes"] = None
            return ep
        finally:
            conn.close()

    def update_intent_episode(self, episode_id: str, purpose: Optional[str] = None, intended_minutes: Optional[float] = None, timer_mode: Optional[str] = None) -> Optional[Dict[str, Any]]:
        conn = get_db_connection()
        now_utc = datetime.now(timezone.utc).isoformat()
        try:
            with conn:
                if purpose == "no_timer":
                    purpose = "unknown"
                    timer_mode = "no_timer"
                    intended_minutes = None

                if purpose and purpose in VALID_PURPOSES:
                    conn.execute("UPDATE intent_episodes SET purpose = ?, updated_at_utc = ? WHERE episode_id = ?", (purpose, now_utc, episode_id))
                if intended_minutes is not None:
                    conn.execute("UPDATE intent_episodes SET intended_minutes = ?, original_intended_minutes = COALESCE(original_intended_minutes, ?), updated_at_utc = ? WHERE episode_id = ?", (intended_minutes, intended_minutes, now_utc, episode_id))
                if timer_mode and timer_mode in VALID_TIMER_MODES:
                    conn.execute("UPDATE intent_episodes SET timer_mode = ?, updated_at_utc = ? WHERE episode_id = ?", (timer_mode, now_utc, episode_id))
            return self.get_intent_episode(episode_id)
        finally:
            conn.close()

    def add_extension_minutes(self, session_id: str, minutes: float = 5.0) -> Optional[Dict[str, Any]]:
        session = self.get_technical_session(session_id)
        if not session or not session.get("episode_id"):
            return None
        episode_id = session["episode_id"]
        now_utc = datetime.now(timezone.utc).isoformat()
        conn = get_db_connection()
        try:
            with conn:
                conn.execute(
                    "UPDATE intent_episodes SET extension_minutes = COALESCE(extension_minutes, 0.0) + ?, updated_at_utc = ? WHERE episode_id = ?",
                    (minutes, now_utc, episode_id)
                )
            return self.get_intent_episode(episode_id)
        finally:
            conn.close()

    def create_technical_session(self, user_id: str, domain: str, episode_id: Optional[str] = None, local_timezone: str = "UTC") -> Dict[str, Any]:
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        now_utc = datetime.now(timezone.utc).isoformat()
        conn = get_db_connection()
        try:
            with conn:
                conn.execute(
                    """INSERT INTO technical_sessions
                       (session_id, episode_id, user_id, domain, started_at_utc, status, local_timezone, created_at_utc, updated_at_utc)
                       VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?)""",
                    (session_id, episode_id, user_id, domain, now_utc, local_timezone, now_utc, now_utc)
                )
            return self.get_technical_session(session_id)
        finally:
            conn.close()

    def get_technical_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM technical_sessions WHERE session_id = ?", (session_id,))
            row = cur.fetchone()
            if not row:
                return None
            session = dict(row)
            if session.get("episode_id"):
                session["intent"] = self.get_intent_episode(session["episode_id"])
            return session
        finally:
            conn.close()

    def add_activity_batch(self, session_id: str, user_id: str, domain: str, activities: List[Dict[str, Any]]) -> int:
        conn = get_db_connection()
        now_utc = datetime.now(timezone.utc).isoformat()
        added_count = 0
        inserted_activities = []
        try:
            with conn:
                for act in activities:
                    client_event_id = act.get("client_event_id") or f"evt_{uuid.uuid4().hex}"
                    event_timestamp_utc = act.get("event_timestamp_utc") or now_utc
                    event_type = act.get("event_type", "focus_heartbeat")
                    duration_ms = act.get("focused_duration_ms")
                    
                    cur = conn.cursor()
                    cur.execute(
                        """INSERT INTO session_activities
                           (client_event_id, session_id, user_id, domain, event_timestamp_utc, received_at_utc, event_type, focused_duration_ms)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                           ON CONFLICT(client_event_id) DO NOTHING""",
                        (client_event_id, session_id, user_id, domain, event_timestamp_utc, now_utc, event_type, duration_ms)
                    )
                    if cur.rowcount > 0:
                        added_count += 1
                        inserted_activities.append(act)

                if added_count > 0:
                    cur = conn.cursor()
                    cur.execute("SELECT episode_id FROM technical_sessions WHERE session_id = ?", (session_id,))
                    row = cur.fetchone()
                    if row and row[0]:
                        ep_id = row[0]
                        conn.execute(
                            "UPDATE intent_episodes SET last_activity_at_utc = ?, last_focused_at_utc = ?, unfocused_at_utc = NULL, updated_at_utc = ? WHERE episode_id = ?",
                            (now_utc, now_utc, now_utc, ep_id)
                        )
            self.last_inserted_activities = inserted_activities
            return added_count
        finally:
            conn.close()

    def update_session_outcome(self, session_id: str, user_id: str, actual_focused_minutes: float, intended_minutes: Optional[float] = None, optimized_target: Optional[float] = None, user_action: Optional[str] = None) -> Dict[str, Any]:
        if intended_minutes is not None:
            planned_minutes = min(actual_focused_minutes, intended_minutes)
            unplanned_minutes = max(0.0, actual_focused_minutes - intended_minutes)
            unknown_minutes = 0.0
        else:
            planned_minutes = 0.0
            unplanned_minutes = 0.0
            unknown_minutes = actual_focused_minutes

        now_utc = datetime.now(timezone.utc).isoformat()
        conn = get_db_connection()
        try:
            with conn:
                conn.execute(
                    """INSERT INTO session_outcomes
                       (session_id, user_id, actual_focused_minutes, planned_minutes, unplanned_minutes, unknown_minutes, optimized_target, user_action, created_at_utc)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(session_id) DO UPDATE SET
                           actual_focused_minutes = excluded.actual_focused_minutes,
                           planned_minutes = excluded.planned_minutes,
                           unplanned_minutes = excluded.unplanned_minutes,
                           unknown_minutes = excluded.unknown_minutes,
                           optimized_target = COALESCE(excluded.optimized_target, session_outcomes.optimized_target),
                           user_action = COALESCE(excluded.user_action, session_outcomes.user_action)""",
                    (session_id, user_id, actual_focused_minutes, planned_minutes, unplanned_minutes, unknown_minutes, optimized_target, user_action, now_utc)
                )
            cur = conn.cursor()
            cur.execute("SELECT * FROM session_outcomes WHERE session_id = ?", (session_id,))
            row = cur.fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def get_reopen_count(self, episode_id: Optional[str]) -> int:
        if not episode_id:
            return 0
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM technical_sessions WHERE episode_id = ?", (episode_id,))
            row = cur.fetchone()
            cnt = row[0] if row else 1
            return max(0, cnt - 1)
        finally:
            conn.close()

    def get_historical_overrun_rate(self, user_id: str) -> float:
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT actual_focused_minutes, planned_minutes FROM session_outcomes WHERE user_id = ? AND planned_minutes IS NOT NULL AND planned_minutes > 0", (user_id,))
            rows = cur.fetchall()
            if not rows:
                return 0.0
            overruns = sum(1 for r in rows if r[0] > r[1])
            return round(overruns / float(len(rows)), 4)
        finally:
            conn.close()

    def get_ordered_cross_domain_switches(self, user_id: str, days: int = 1) -> int:
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            cur.execute(
                """SELECT domain FROM technical_sessions
                   WHERE user_id = ? AND started_at_utc >= ?
                   ORDER BY started_at_utc ASC""",
                (user_id, cutoff)
            )
            rows = cur.fetchall()
            if not rows:
                return 0

            domains = [r[0] for r in rows if r[0]]
            switches = 0
            prev_domain = None
            for d in domains:
                if prev_domain is not None and d != prev_domain:
                    switches += 1
                prev_domain = d
            return switches
        finally:
            conn.close()
