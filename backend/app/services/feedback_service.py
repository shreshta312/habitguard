"""
feedback_service.py

Validates and persists feedback events, then delegates to PersonalAdaptationService.
Never modifies personal parameters directly.
Stores the adaptation trace returned by PersonalAdaptationService.
"""
from typing import Dict, Any, Optional

from app.db.repositories.feedback import FeedbackRepository
from app.services.personal_adaptation_service import PersonalAdaptationService


class FeedbackService:
    """
    Fix 4 wiring:
      1. Persist FeedbackEvent via FeedbackRepository.
      2. Pass persisted event + full session_context to PersonalAdaptationService.
      3. Adaptation trace is returned in the response (exposed via research route).
      4. This service never touches PersonalParametersRepository directly.
    """

    def __init__(
        self,
        feedback_repo: Optional[FeedbackRepository] = None,
        adaptation_service: Optional[PersonalAdaptationService] = None,
    ) -> None:
        self.repo = feedback_repo or FeedbackRepository()
        self.adaptation = adaptation_service or PersonalAdaptationService()

    def record_action(
        self,
        session_id: str,
        user_id: str,
        action: str,
        task_completion: Optional[str] = None,
        time_sufficient: Optional[str] = None,
        session_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Persist the event, then trigger adaptation.
        Returns the persisted event dict enriched with adaptation_trace.
        """
        # Step 1 – persist
        event = self.repo.add_feedback_event(
            session_id=session_id,
            user_id=user_id,
            action=action,
            task_completion=task_completion,
            time_sufficient=time_sufficient,
        )

        # Step 2 – adaptation runs only after persistence succeeds
        ctx = session_context or {}
        ctx.setdefault("session_id", session_id)
        # Merge task_completion / time_sufficient into the persisted event so
        # PersonalAdaptationService sees them without querying the DB again.
        event_with_signals = {
            **event,
            "task_completion": task_completion,
            "time_sufficient": time_sufficient,
        }
        trace = self.adaptation.process_feedback_event(event_with_signals, ctx)

        event["adaptation_trace"] = trace
        return event

    def save_event(self, event: Any) -> Dict[str, Any]:
        """
        Legacy / generic event saver (used by /feedback/event endpoint).
        Persists first, then triggers adaptation.
        """
        if hasattr(event, "model_dump"):
            payload = event.model_dump()
        elif hasattr(event, "dict"):
            payload = event.dict()
        else:
            payload = dict(event)

        user_id    = payload.get("user_id", "local_user")
        action     = payload.get("event_type") or payload.get("action") or "dismiss"
        session_id = payload.get("session_id") or "legacy_session"

        recorded = self.record_action(
            session_id=session_id,
            user_id=user_id,
            action=action,
            task_completion=payload.get("task_completion"),
            time_sufficient=payload.get("time_sufficient"),
            session_context=payload.get("context"),
        )

        return {
            "success":  True,
            "status":   "success",
            "message":  "Feedback event saved successfully",
            "event_id": recorded.get("id"),
            "event":    payload,
        }

    def get_summary(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        target_user = user_id or "local_user"
        summary = self.repo.get_user_feedback_summary(target_user)

        total      = summary.get("total_events", 0)
        acceptance = summary.get("acceptance_rate", 0.5)

        most_dismissed = self.repo.get_most_dismissed_sites(target_user)

        return {
            "total_events": total,
            "event_type_counts": {
                "overlay_dismissed": summary.get("dismiss_count", 0),
                "break_accepted":    summary.get("finish_count", 0) + summary.get("extend_count", 0),
            },
            "overlay_dismissed_count":  summary.get("dismiss_count", 0),
            "break_accepted_count":     summary.get("finish_count", 0) + summary.get("extend_count", 0),
            "break_acceptance_rate":    acceptance,
            "acceptance_rate":          acceptance,
            "most_dismissed_sites":     most_dismissed,
            "most_accepted_break_sites": [],
            "site_actions":             {},
        }


feedback_service = FeedbackService()