import json
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from app.schemas.feedback_schema import FeedbackEvent
from app.services.database import db_manager


class FeedbackService:
    """
    Stores and summarizes user feedback events.

    For live intervention adaptation, summaries are bounded to recent events
    so old feedback does not dominate forever and the decision loop stays fast.
    """

    def __init__(self):
        pass

    def save_event(self, event: FeedbackEvent):
        event_id = str(uuid.uuid4())

        if hasattr(event, "model_dump"):
            payload = event.model_dump()
        else:
            payload = event.dict()

        payload["event_id"] = event_id
        
        now = datetime.now(timezone.utc).isoformat()
        payload["server_received_at"] = now

        if not payload.get("timestamp"):
            payload["timestamp"] = now

        user_id = payload.get("user_id", "local_user")
        event_type = payload.get("event_type", "unknown")
        timestamp = payload.get("timestamp")

        db_manager.save_feedback_event(
            event_id=event_id,
            user_id=user_id,
            event_type=event_type,
            timestamp=timestamp,
            server_received_at=now,
            payload=payload
        )

        return {
            "success": True,
            "event_id": event_id,
            "message": "Feedback event saved successfully"
        }

    def load_events(self):
        return db_manager.load_feedback_events()

    def get_summary(self, user_id=None, recent_limit=200):
        events = self.load_events()

        if user_id is not None:
            events = [
                event for event in events
                if str(event.get("user_id", "local_user")) == str(user_id)
            ]

        # Use only recent feedback for live adaptation.
        # This keeps the intervention loop responsive and prevents very old
        # behavior from dominating current personalization.
        if recent_limit is not None and recent_limit > 0:
            events = events[-recent_limit:]

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
            "user_id": user_id,
            "recent_limit": recent_limit,
            "total_events": total_events,
            "event_type_counts": dict(event_type_counts),
            "overlay_dismissed_count": overlay_dismissed_count,
            "break_accepted_count": break_accepted_count,
            "break_acceptance_rate": break_acceptance_rate,
            "most_dismissed_sites": dismissed_sites.most_common(5),
            "most_accepted_break_sites": accepted_break_sites.most_common(5)
        }


feedback_service = FeedbackService()