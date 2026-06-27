import pickle
import pandas as pd
from pathlib import Path


MODEL_PATH = Path("../ml/saved_models/user_segmentation.pkl")


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
        """
        Heuristic segment label based on scaled feature values.

        Thresholds (0.8, 0.5, -0.8) are relative to the standard-scaled
        feature space used during model training. These are not raw hours.
        """

        if features["daily_screen_time_hours"] > 0.8 and features["social_media_hours"] > 0.8:
            return "Heavy Social User"

        elif features["gaming_hours"] > 0.8:
            return "Gaming Heavy User"

        elif features["work_study_hours"] > 0.8 and features["daily_screen_time_hours"] < 0.5:
            return "Productivity Focused User"

        elif features["sleep_hours"] < -0.8 and features["daily_screen_time_hours"] > 0.5:
            return "Late Night / High Usage User"

        else:
            return "Balanced User"

    def predict_segment(self, features):
        sample = pd.DataFrame([features])

        cluster = self.model.predict(sample)[0]
        segment_name = self.get_segment_name(features)

        return {
            "cluster": int(cluster),
            "segment_name": segment_name
        }