from fastapi import APIRouter, HTTPException

from app.schemas.feedback_schema import FeedbackEvent
from app.services.feedback_service import feedback_service


router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("/event")
def save_feedback_event(event: FeedbackEvent):
    try:
        return feedback_service.save_event(event)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save feedback event: {str(e)}"
        )