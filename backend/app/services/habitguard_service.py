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

    Note: df is loaded once at FastAPI startup in main.py and passed
    into service methods directly. Methods here call load_data() only
    when invoked standalone (e.g. tests). In production, the df loaded
    at startup is used via the dataset_service passed to each method.
    """

    def __init__(self, csv_path):
        self.dataset_service = DatasetService(csv_path)
        self.addiction_engine = AddictionEngine()
        self.limit_engine = DynamicLimitEngine()
        self._df = None

    def _get_df(self):
        """
        Returns a cached DataFrame. Loads from disk only on first call.
        Prevents re-reading the CSV on every API request.
        """

        if self._df is None:
            self._df = self.dataset_service.load_data()

        return self._df

    def get_user_daily_summary(self, user_id):
        df = self._get_df()

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

        current_score = self.addiction_engine.current_score(daily_usage_history)
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

    def get_user_app_summary(self, user_id, app_name):
        df = self._get_df()

        usage_history = self.dataset_service.get_user_app_usage(
            df,
            user_id,
            app_name
        )

        if len(usage_history) == 0:
            return {
                "user_id": user_id,
                "app_name": app_name,
                "error": "No usage data found for this user and app"
            }

        addiction_scores = self.addiction_engine.calculate_scores(usage_history)
        current_score = self.addiction_engine.current_score(usage_history)
        score_level = self.addiction_engine.score_level(current_score)
        recommended_limit = self.limit_engine.recommend_limit(current_score)

        friction = self.limit_engine.friction_action(
            usage_today=usage_history[-1],
            recommended_limit=recommended_limit
        )

        return {
            "user_id": user_id,
            "app_name": app_name,
            "usage_history": usage_history,
            "addiction_scores": addiction_scores,
            "current_score": current_score,
            "score_level": score_level,
            "recommended_limit": recommended_limit,
            "today_usage": usage_history[-1],
            "friction_action": friction
        }