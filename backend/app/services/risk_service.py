import pickle
from pathlib import Path
from typing import Any

import pandas as pd


MODEL_PATH = (
    Path(__file__).resolve().parents[3]
    / "ml"
    / "saved_models"
    / "risk_classifier.pkl"
)


class RiskService:
    def __init__(self) -> None:
        self.model: Any | None = None
        self.load_error: str | None = None

        try:
            if not MODEL_PATH.exists():
                self.load_error = (
                    f"Risk model was not found at {MODEL_PATH}."
                )
                return

            with open(MODEL_PATH, "rb") as file:
                self.model = pickle.load(file)

        except Exception as error:
            self.model = None
            self.load_error = str(error)

    def predict_risk(self, features: dict) -> dict:
        if self.model is None:
            return {
                "success": False,
                "model_loaded": False,
                "model_role": "supporting_dashboard_analytics",
                "used_in_live_intervention_loop": False,
                "prediction": None,
                "risk_result": "UNAVAILABLE",
                "not_addicted_probability": None,
                "addicted_probability": None,
                "error": (
                    self.load_error
                    or "The risk model is currently unavailable."
                ),
            }

        try:
            sample = pd.DataFrame([features])

            prediction = int(self.model.predict(sample)[0])
            probability = self.model.predict_proba(sample)[0]

            if prediction == 1:
                result = "HIGH ADDICTION RISK"
            else:
                result = "LOW ADDICTION RISK"

            return {
                "success": True,
                "model_loaded": True,
                "model_role": "supporting_dashboard_analytics",
                "used_in_live_intervention_loop": False,
                "analytics_purpose": (
                    "Estimates overall addiction risk for dashboard "
                    "awareness. Live interventions are handled by "
                    "StructuralTimerEngine and DecisionEngine."
                ),
                "prediction": prediction,
                "risk_result": result,
                "not_addicted_probability": round(
                    float(probability[0]) * 100,
                    2,
                ),
                "addicted_probability": round(
                    float(probability[1]) * 100,
                    2,
                ),
            }

        except Exception as error:
            return {
                "success": False,
                "model_loaded": True,
                "model_role": "supporting_dashboard_analytics",
                "used_in_live_intervention_loop": False,
                "prediction": None,
                "risk_result": "UNAVAILABLE",
                "not_addicted_probability": None,
                "addicted_probability": None,
                "error": f"Risk prediction failed: {error}",
            }


risk_service = RiskService()