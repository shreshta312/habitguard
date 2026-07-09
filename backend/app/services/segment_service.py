import pickle
from pathlib import Path

import pandas as pd


MODEL_PATH = (
    Path(__file__).resolve().parents[3]
    / "ml"
    / "saved_models"
    / "user_segmentation.pkl"
)


class SegmentService:
    def __init__(self):
        try:
            with open(MODEL_PATH, "rb") as file:
                self.model = pickle.load(file)

        except FileNotFoundError as e:
            raise RuntimeError(
                f"SegmentService failed to load model file: {e}. "
                f"Expected at {MODEL_PATH}."
            )

    def get_segment_name(self, features):
        if (
            features["daily_screen_time_hours"] > 0.8
            and features["social_media_hours"] > 0.8
        ):
            return "Heavy Social User"

        if features["gaming_hours"] > 0.8:
            return "Gaming Heavy User"

        if (
            features["work_study_hours"] > 0.8
            and features["daily_screen_time_hours"] < 0.5
        ):
            return "Productivity Focused User"

        if (
            features["sleep_hours"] < -0.8
            and features["daily_screen_time_hours"] > 0.5
        ):
            return "Late Night / High Usage User"

        return "Balanced User"

    def predict_segment(self, features):
        sample = pd.DataFrame([features])

        cluster = self.model.predict(sample)[0]
        segment_name = self.get_segment_name(features)

        return {
            "model_role": "supporting_dashboard_analytics",
            "used_in_live_intervention_loop": False,
            "analytics_purpose": (
                "Groups users into behavior segments for dashboard personalization. "
                "Live interventions are handled by StructuralTimerEngine and DecisionEngine."
            ),
            "cluster": int(cluster),
            "segment_name": segment_name,
        }


segment_service = SegmentService()