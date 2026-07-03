from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class UsageSnapshot(BaseModel):
    user_id: str = "local_user"
    date: Optional[str] = None

    daily_usage_minutes: Dict[str, float] = {}
    domain_usage_minutes: Dict[str, Dict[str, float]] = {}

    current_session: Optional[Dict[str, Any]] = None
    session_history: List[Dict[str, Any]] = []

    latest_intervention: Optional[Dict[str, Any]] = None
    active_intervention_timer: Optional[Dict[str, Any]] = None

    source: str = "chrome_extension"