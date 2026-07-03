import json
import uuid
from collections import Counter
from datetime import datetime, timezone
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
            "message": "Usage snapshot saved successfully"
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
            reverse=True
        )

        return {
            "user_id": user_id,
            "total_snapshots": len(snapshots),
            "limit": limit,
            "snapshots": snapshots[:limit]
        }

    def get_summary(self, user_id="local_user"):
        snapshots = self.load_snapshots(user_id=user_id)

        if len(snapshots) == 0:
            return {
                "user_id": user_id,
                "total_snapshots": 0,
                "message": "No usage snapshots found for this user."
            }

        latest = sorted(
            snapshots,
            key=lambda item: item.get("server_received_at", "")
        )[-1]

        daily_usage_minutes = latest.get("daily_usage_minutes", {}) or {}
        domain_usage_minutes = latest.get("domain_usage_minutes", {}) or {}

        latest_date = latest.get("date")
        today_total = daily_usage_minutes.get(latest_date, 0)

        latest_day_domains = domain_usage_minutes.get(latest_date, {}) or {}

        top_domains = sorted(
            latest_day_domains.items(),
            key=lambda item: item[1],
            reverse=True
        )[:5]

        intervention_counts = Counter()

        for snapshot in snapshots:
            intervention = snapshot.get("latest_intervention") or {}
            intervention_type = intervention.get("intervention_type")

            if intervention_type:
                intervention_counts[intervention_type] += 1

        return {
            "user_id": user_id,
            "total_snapshots": len(snapshots),
            "latest_date": latest_date,
            "today_total_usage_minutes": today_total,
            "top_domains_today": [
                {
                    "domain": domain,
                    "minutes": minutes
                }
                for domain, minutes in top_domains
            ],
            "current_session": latest.get("current_session"),
            "latest_intervention": latest.get("latest_intervention"),
            "active_intervention_timer": latest.get("active_intervention_timer"),
            "intervention_type_counts": dict(intervention_counts)
        }


usage_service = UsageService()