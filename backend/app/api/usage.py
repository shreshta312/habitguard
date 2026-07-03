from fastapi import APIRouter, HTTPException

from app.schemas.usage_schema import UsageSnapshot
from app.services.usage_service import usage_service


router = APIRouter(prefix="/usage", tags=["usage"])


@router.post("/snapshot")
def save_usage_snapshot(snapshot: UsageSnapshot):
    try:
        return usage_service.save_snapshot(snapshot)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save usage snapshot: {str(e)}"
        )


@router.get("/history/{user_id}")
def get_usage_history(user_id: str, limit: int = 30):
    try:
        return usage_service.get_history(user_id=user_id, limit=limit)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load usage history: {str(e)}"
        )


@router.get("/summary/{user_id}")
def get_usage_summary(user_id: str):
    try:
        return usage_service.get_summary(user_id=user_id)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load usage summary: {str(e)}"
        )