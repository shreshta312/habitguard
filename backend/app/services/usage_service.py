import json
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.schemas.usage_schema import UsageSnapshot


class UsageService:
    """
    Stores Chrome extension usage snapshots for dashboard/history use.

    Chrome storage remains the short-term live tracker.
    This service stores longer-term backend snapshots in JSONL format.
    """

    def __init__(self):
        self.data_dir = Path(__file__).resolve().parents[2] / "data"
        self.usage_file = self.data_dir / "usage_snapshots.jsonl"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def save_snapshot(self, snapshot: UsageSnapshot):
        snapshot_id = str(uuid.uuid4())

        if hasattr(snapshot, "model_dump"):
            payload = snapshot.model_dump()
        else:
            payload = snapshot.dict()

        now = datetime.now(timezone.utc).isoformat()

        payload["snapshot_id"] = snapshot_id
        payload["server_received_at"] = now

        if not payload.get("date"):
            payload["date"] = datetime.now(timezone.utc).date().isoformat()

        with open(self.usage_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, default=str) + "\n")

        return {
            "success": True,
            "snapshot_id": snapshot_id,
            "message": "Usage snapshot saved successfully",
        }

    def load_snapshots(self, user_id=None):
        if not self.usage_file.exists():
            return []

        snapshots = []

        with open(self.usage_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                if not line:
                    continue

                try:
                    snapshot = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if user_id is not None:
                    if str(snapshot.get("user_id", "local_user")) != str(user_id):
                        continue

                snapshots.append(snapshot)

        return snapshots

    def get_history(self, user_id="local_user", limit=30):
        snapshots = self.load_snapshots(user_id=user_id)

        snapshots = sorted(
            snapshots,
            key=lambda item: item.get("server_received_at", ""),
            reverse=True,
        )

        return {
            "user_id": user_id,
            "total_snapshots": len(snapshots),
            "limit": limit,
            "snapshots": snapshots[:limit],
        }

    def get_daily_usage_history(self, user_id="local_user"):
        snapshots = self.load_snapshots(user_id=user_id)

        daily_usage_by_date = {}

        for snapshot in snapshots:
            daily_usage_minutes = snapshot.get("daily_usage_minutes", {}) or {}

            for date_key, minutes in daily_usage_minutes.items():
                try:
                    daily_usage_by_date[date_key] = float(minutes)
                except (TypeError, ValueError):
                    daily_usage_by_date[date_key] = 0.0

        daily_usage_history = [
            {
                "date": date_key,
                "minutes": daily_usage_by_date[date_key],
            }
            for date_key in sorted(daily_usage_by_date.keys())
        ]

        return {
            "user_id": user_id,
            "days_available": len(daily_usage_history),
            "daily_usage_history": daily_usage_history,
            "usage_history_minutes": [
                item["minutes"] for item in daily_usage_history
            ],
        }

    def get_summary(self, user_id="local_user"):
        snapshots = self.load_snapshots(user_id=user_id)

        if len(snapshots) == 0:
            return {
                "user_id": user_id,
                "total_snapshots": 0,
                "message": "No usage snapshots found for this user.",
                "dashboard_ready": False,
            }

        snapshots = sorted(
            snapshots,
            key=lambda item: item.get("server_received_at", ""),
        )

        latest = snapshots[-1]

        daily_usage_by_date = {}
        domain_usage_by_date = {}

        source_counts = Counter()
        intervention_type_counts = Counter()
        usage_status_counts = Counter()
        friction_type_counts = Counter()

        for snapshot in snapshots:
            source = snapshot.get("source") or "unknown_source"
            source_counts[source] += 1

            daily_usage_minutes = snapshot.get("daily_usage_minutes", {}) or {}

            for date_key, minutes in daily_usage_minutes.items():
                try:
                    daily_usage_by_date[date_key] = float(minutes)
                except (TypeError, ValueError):
                    daily_usage_by_date[date_key] = 0.0

            domain_usage_minutes = snapshot.get("domain_usage_minutes", {}) or {}

            for date_key, domains in domain_usage_minutes.items():
                if not isinstance(domains, dict):
                    continue

                if date_key not in domain_usage_by_date:
                    domain_usage_by_date[date_key] = {}

                for domain, minutes in domains.items():
                    try:
                        domain_usage_by_date[date_key][domain] = float(minutes)
                    except (TypeError, ValueError):
                        domain_usage_by_date[date_key][domain] = 0.0

            intervention = snapshot.get("latest_intervention") or {}

            if isinstance(intervention, dict):
                intervention_type = intervention.get("intervention_type")
                usage_status = intervention.get("usage_status")
                friction_type = intervention.get("friction_type")
            else:
                intervention_type = None
                usage_status = None
                friction_type = None

            if intervention_type:
                intervention_type_counts[intervention_type] += 1

            if usage_status:
                usage_status_counts[usage_status] += 1

            if friction_type:
                friction_type_counts[friction_type] += 1

        latest_date = latest.get("date")

        if not latest_date and daily_usage_by_date:
            latest_date = sorted(daily_usage_by_date.keys())[-1]

        today_total = daily_usage_by_date.get(latest_date, 0.0)

        latest_day_domains = domain_usage_by_date.get(latest_date, {}) or {}

        top_domains_today = sorted(
            latest_day_domains.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:5]

        all_domain_totals = Counter()

        for date_domains in domain_usage_by_date.values():
            for domain, minutes in date_domains.items():
                all_domain_totals[domain] += minutes

        top_domains_all_time = all_domain_totals.most_common(10)

        usage_trend_7_days = []

        if latest_date:
            try:
                end_date = datetime.strptime(latest_date, "%Y-%m-%d").date()

                for offset in range(6, -1, -1):
                    day = end_date - timedelta(days=offset)
                    day_key = day.isoformat()

                    usage_trend_7_days.append(
                        {
                            "date": day_key,
                            "minutes": daily_usage_by_date.get(day_key, 0.0),
                        }
                    )

            except ValueError:
                for date_key in sorted(daily_usage_by_date.keys())[-7:]:
                    usage_trend_7_days.append(
                        {
                            "date": date_key,
                            "minutes": daily_usage_by_date.get(date_key, 0.0),
                        }
                    )

        latest_session_history = latest.get("session_history", []) or []

        session_durations = []

        for session in latest_session_history:
            duration = (
                session.get("durationMinutes")
                or session.get("sessionMinutes")
                or 0
            )

            try:
                session_durations.append(float(duration))
            except (TypeError, ValueError):
                continue

        total_sessions = len(session_durations)
        total_session_minutes = sum(session_durations)

        average_session_minutes = (
            round(total_session_minutes / total_sessions, 2)
            if total_sessions > 0
            else 0.0
        )

        longest_session_minutes = (
            round(max(session_durations), 2)
            if session_durations
            else 0.0
        )

        timer_started_count = source_counts.get(
            "chrome_extension_timer_started",
            0,
        )

        timer_cleared_count = source_counts.get(
            "chrome_extension_timer_cleared",
            0,
        )

        category_updated_count = source_counts.get(
            "chrome_extension_category_updated",
            0,
        )

        return {
            "user_id": user_id,
            "dashboard_ready": True,

            "total_snapshots": len(snapshots),
            "latest_snapshot_id": latest.get("snapshot_id"),
            "latest_date": latest_date,
            "latest_received_at": latest.get("server_received_at"),

            "today_total_usage_minutes": round(today_total, 2),

            "usage_trend_7_days": usage_trend_7_days,

            "top_domains_today": [
                {
                    "domain": domain,
                    "minutes": round(minutes, 2),
                }
                for domain, minutes in top_domains_today
            ],

            "top_domains_all_time": [
                {
                    "domain": domain,
                    "minutes": round(minutes, 2),
                }
                for domain, minutes in top_domains_all_time
            ],

            "current_session": latest.get("current_session"),
            "latest_intervention": latest.get("latest_intervention"),
            "active_intervention_timer": latest.get("active_intervention_timer"),

            "session_stats": {
                "total_sessions": total_sessions,
                "total_session_minutes": round(total_session_minutes, 2),
                "average_session_minutes": average_session_minutes,
                "longest_session_minutes": longest_session_minutes,
            },

            "intervention_stats": {
                "intervention_type_counts": dict(intervention_type_counts),
                "usage_status_counts": dict(usage_status_counts),
                "friction_type_counts": dict(friction_type_counts),
            },

            "extension_event_stats": {
                "source_counts": dict(source_counts),
                "timer_started_count": timer_started_count,
                "timer_cleared_count": timer_cleared_count,
                "category_updated_count": category_updated_count,
            },
        }


usage_service = UsageService()