import pickle
import pandas as pd
from pathlib import Path


MODEL_PATH = Path("../ml/saved_models/anomaly_detector.pkl")
SCALER_PATH = Path("../ml/saved_models/anomaly_scaler.pkl")


class AnomalyService:
    def __init__(self):
        try:
            with open(MODEL_PATH, "rb") as file:
                self.model = pickle.load(file)

            with open(SCALER_PATH, "rb") as file:
                self.scaler = pickle.load(file)

        except FileNotFoundError as e:
            raise RuntimeError(
                f"AnomalyService failed to load model files: {e}. "
                f"Expected at {MODEL_PATH} and {SCALER_PATH}."
            )

    def detect_anomaly(self, screen_time_min, launches, interactions, is_productive):
        sample = pd.DataFrame([{
            "screen_time_min": screen_time_min,
            "launches": launches,
            "interactions": interactions,
            "is_productive": is_productive
        }])

        sample_scaled = self.scaler.transform(sample)

        prediction = self.model.predict(sample_scaled)[0]

        if prediction == -1:
            result = "ANOMALY"
            message = "Unusual usage pattern detected."
        else:
            result = "NORMAL"
            message = "Usage pattern looks normal."

        return {
            "screen_time_min": screen_time_min,
            "launches": launches,
            "interactions": interactions,
            "is_productive": is_productive,
            "result": result,
            "message": message
        }