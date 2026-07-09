import pickle
import pandas as pd
from pathlib import Path

MODEL_PATH = Path(__file__).resolve().parents[3] / "ml" / "saved_models" / "usage_forecaster.pkl"

class ForecasterService:
    def __init__(self):
        self.model = None
        try:
            if MODEL_PATH.exists():
                with open(MODEL_PATH, "rb") as file:
                    self.model = pickle.load(file)
            else:
                print(f"Warning: Forecaster model not found at {MODEL_PATH}")
        except Exception as e:
            print(f"Error loading Forecaster model: {e}")

    def predict_next_usage(self, daily_history_minutes, today_launches=10, today_interactions=150, today_is_productive=1):
        """
        Predicts tomorrow's screen time in minutes using historical lags.
        daily_history_minutes should be a list of daily screen times in chronological order,
        including today's current usage at the end.
        """
        if self.model is None:
            return {
                "success": False,
                "error": "Forecaster model is not loaded.",
                "forecast_minutes": None
            }

        # We need at least 3 days of history (today, yesterday, and day before yesterday)
        if len(daily_history_minutes) < 3:
            return {
                "success": False,
                "error": f"Insufficient history. Need at least 3 days of usage history (Currently: {len(daily_history_minutes)} days).",
                "forecast_minutes": None
            }

        # Features correspond to:
        # lag_1 = today (index -1)
        # lag_2 = yesterday (index -2)
        # lag_3 = 2 days ago (index -3)
        usage_lag_1 = float(daily_history_minutes[-1])
        usage_lag_2 = float(daily_history_minutes[-2])
        usage_lag_3 = float(daily_history_minutes[-3])
        
        usage_rolling_mean_3 = (usage_lag_1 + usage_lag_2 + usage_lag_3) / 3.0
        
        launches_lag_1 = float(today_launches)
        interactions_lag_1 = float(today_interactions)
        is_productive = float(today_is_productive)

        features = pd.DataFrame([{
            "usage_lag_1": usage_lag_1,
            "usage_lag_2": usage_lag_2,
            "usage_lag_3": usage_lag_3,
            "usage_rolling_mean_3": usage_rolling_mean_3,
            "launches_lag_1": launches_lag_1,
            "interactions_lag_1": interactions_lag_1,
            "is_productive": is_productive
        }])

        try:
            prediction = self.model.predict(features)[0]
            # Ensure forecast screen time is non-negative
            forecast_minutes = max(0.0, round(float(prediction), 2))
            
            # Estimate confidence level based on amount of history
            history_days = len(daily_history_minutes)
            if history_days >= 10:
                confidence = "HIGH"
            elif history_days >= 5:
                confidence = "MEDIUM"
            else:
                confidence = "LOW"

            return {
                "success": True,
                "forecast_minutes": forecast_minutes,
                "confidence": confidence,
                "features_used": {
                    "usage_lag_1": round(usage_lag_1, 2),
                    "usage_lag_2": round(usage_lag_2, 2),
                    "usage_lag_3": round(usage_lag_3, 2),
                    "usage_rolling_mean_3": round(usage_rolling_mean_3, 2),
                    "launches_lag_1": launches_lag_1,
                    "interactions_lag_1": interactions_lag_1,
                    "is_productive": is_productive
                }
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Forecaster prediction failed: {str(e)}",
                "forecast_minutes": None
            }

forecaster_service = ForecasterService()
