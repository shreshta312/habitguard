import json
import uuid
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


feedback_service = FeedbackService()