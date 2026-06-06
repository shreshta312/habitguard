from app.services.dataset_service import DatasetService
from app.services.addiction_engine import AddictionEngine
from app.services.dynamic_limit_engine import DynamicLimitEngine


class HabitGuardService:
    """
    Main service that combines:
    - dataset loading
    - addiction score calculation
    - dynamic limit recommendation
    - friction decision
    """

    def __init__(self, csv_path):
        self.dataset_service = DatasetService(csv_path)
        self.addiction_engine = AddictionEngine()
        self.limit_engine = DynamicLimitEngine()

    def get_user_daily_summary(self, user_id):
        df = self.dataset_service.load_data()

        daily_usage_history = self.dataset_service.get_user_daily_total_usage(
            df,
            user_id
        )

        if len(daily_usage_history) == 0:
            return {
                "user_id": user_id,
                "error": "No usage data found for this user"
            }

        addiction_scores = self.addiction_engine.calculate_scores(
            daily_usage_history
        )

        current_score = self.addiction_engine.current_score(
            daily_usage_history
        )

        score_level = self.addiction_engine.score_level(current_score)

        recommended_limit = self.limit_engine.recommend_limit(current_score)

        friction = self.limit_engine.friction_action(
            usage_today=daily_usage_history[-1],
            recommended_limit=recommended_limit
        )

        return {
            "user_id": user_id,
            "daily_usage_history": daily_usage_history,
            "addiction_scores": addiction_scores,
            "current_score": current_score,
            "score_level": score_level,
            "recommended_limit": recommended_limit,
            "today_usage": daily_usage_history[-1],
            "friction_action": friction
        }