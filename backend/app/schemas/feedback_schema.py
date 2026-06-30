from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class FeedbackEvent(BaseModel):
    user_id: str = "local_user"

    event_type: str = Field(
        ...,
        description="overlay_dismissed, break_accepted, break_completed, break_skipped"
    )

    site: Optional[str] = None
    category: Optional[str] = None
    overlay_id: Optional[str] = None

    decision: Optional[str] = None
    reason: Optional[str] = None

    timestamp: Optional[str] = None

    context: Dict[str, Any] = {}