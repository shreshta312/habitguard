from typing import Dict, Any, Optional
from app.db.repositories.sessions import SessionsRepository

class SessionIntentService:
    """
    Manages technical sessions and user-intent episodes cleanly.
    Ensures strict purpose options and timer_mode separation.
    """
    def __init__(self, repo: Optional[SessionsRepository] = None):
        self.repo = repo or SessionsRepository()

    def start_session(
        self,
        user_id: str,
        domain: str,
        purpose: Optional[str] = "unknown",
        intended_minutes: Optional[float] = None,
        timer_mode: str = "planned",
        remember_today: bool = False,
        local_timezone: str = "UTC"
    ) -> Dict[str, Any]:
        # Step 1: Resolve or resume Intent Episode
        episode = self.repo.resolve_intent_episode(
            user_id=user_id,
            domain=domain,
            purpose=purpose or "unknown",
            intended_minutes=intended_minutes,
            timer_mode=timer_mode,
            remember_today=remember_today
        )

        # Step 2: Create Technical Session tied to Intent Episode
        tech_session = self.repo.create_technical_session(
            user_id=user_id,
            domain=domain,
            episode_id=episode["episode_id"],
            local_timezone=local_timezone
        )

        tech_session["intent"] = episode
        tech_session["episode_focused_minutes"] = self.repo.get_episode_focused_minutes(episode["episode_id"])
        return tech_session

    def update_intent(
        self,
        session_id: str,
        purpose: Optional[str] = None,
        intended_minutes: Optional[float] = None,
        timer_mode: Optional[str] = None
    ) -> Dict[str, Any]:
        session = self.repo.get_technical_session(session_id)
        if not session or not session.get("episode_id"):
            return session or {}

        updated_intent = self.repo.update_intent_episode(
            episode_id=session["episode_id"],
            purpose=purpose,
            intended_minutes=intended_minutes,
            timer_mode=timer_mode
        )
        session["intent"] = updated_intent
        return session

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self.repo.get_technical_session(session_id)
