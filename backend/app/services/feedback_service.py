import json
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from app.schemas.feedback_schema import FeedbackEvent


class FeedbackService:
    def __init__(self):
        self.data_dir = Path(__file__).resolve().parents[2] / "data"
        self.feedback_file = self.data_dir / "feedback_events.jsonl"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def save_event(self, event: FeedbackEvent):
        event_id = str(uuid.uuid4())

        if hasattr(event, "model_dump"):
            payload = event.model_dump()
        else:
            payload = event.dict()

        payload["event_id"] = event_id
        payload["server_received_at"] = datetime.now(timezone.utc).isoformat()

        if not payload.get("timestamp"):
            payload["timestamp"] = datetime.now(timezone.utc).isoformat()

        with open(self.feedback_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, default=str) + "\n")

        return {
            "success": True,
            "event_id": event_id,
            "message": "Feedback event saved successfully"
        }

    def load_events(self):
        if not self.feedback_file.exists():
            return []

        events = []

        with open(self.feedback_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                if not line:
                    continue

                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        return events

    def get_summary(self):
        events = self.load_events()

        total_events = len(events)

        event_type_counts = Counter(
            event.get("event_type", "unknown")
            for event in events
        )

        overlay_dismissed_count = event_type_counts.get("overlay_dismissed", 0)
        break_accepted_count = event_type_counts.get("break_accepted", 0)

        meaningful_intervention_events = (
            overlay_dismissed_count + break_accepted_count
        )

        if meaningful_intervention_events == 0:
            break_acceptance_rate = 0.0
        else:
            break_acceptance_rate = round(
                break_accepted_count / meaningful_intervention_events,
                4
            )

        dismissed_sites = Counter(
            event.get("site", "unknown")
            for event in events
            if event.get("event_type") == "overlay_dismissed"
        )

        accepted_break_sites = Counter(
            event.get("site", "unknown")
            for event in events
            if event.get("event_type") == "break_accepted"
        )

        return {
            "total_events": total_events,
            "event_type_counts": dict(event_type_counts),
            "overlay_dismissed_count": overlay_dismissed_count,
            "break_accepted_count": break_accepted_count,
            "break_acceptance_rate": break_acceptance_rate,
            "most_dismissed_sites": dismissed_sites.most_common(5),
            "most_accepted_break_sites": accepted_break_sites.most_common(5)
        }


feedback_service = FeedbackService()