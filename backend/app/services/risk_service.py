import pickle
import pandas as pd
from pathlib import Path


MODEL_PATH = Path("../ml/saved_models/risk_classifier.pkl")


class RiskService:
    def __init__(self):
        try:
            with open(MODEL_PATH, "rb") as file:
                self.model = pickle.load(file)

        except FileNotFoundError as e:
            raise RuntimeError(
                f"RiskService failed to load model file: {e}. "
                f"Expected at {MODEL_PATH}."
            )

    def predict_risk(self, features):
        sample = pd.DataFrame([features])

        prediction = self.model.predict(sample)[0]
        probability = self.model.predict_proba(sample)[0]

        if prediction == 1:
            result = "HIGH ADDICTION RISK"
        else:
            result = "LOW ADDICTION RISK"

        return {
            "prediction": int(prediction),
            "risk_result": result,
            "not_addicted_probability": round(probability[0] * 100, 2),
            "addicted_probability": round(probability[1] * 100, 2)
        }