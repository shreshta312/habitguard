import pickle
from pathlib import Path
from typing import Any

import pandas as pd


MODEL_PATH = (
    Path(__file__).resolve().parents[3]
    / "ml"
    / "saved_models"
    / "user_segmentation.pkl"
)


class SegmentService:
    def __init__(self) -> None:
        self.pipeline: Any | None = None
        self.feature_columns: list[str] = []
        self.cluster_names: dict[int, str] = {}
        self.load_error: str | None = None

        try:
            if not MODEL_PATH.exists():
                self.load_error = (
                    "Segmentation model was not found at "
                    f"{MODEL_PATH}."
                )
                return

            with open(MODEL_PATH, "rb") as file:
                artifact = pickle.load(file)

            if not isinstance(artifact, dict):
                self.load_error = (
                    "Legacy segmentation model detected. "
                    "Retrain the segmentation model to create "
                    "the complete preprocessing pipeline."
                )
                return

            self.pipeline = artifact.get("pipeline")

            self.feature_columns = list(
                artifact.get(
                    "feature_columns",
                    [],
                )
            )

            self.cluster_names = {
                int(key): value
                for key, value
                in artifact.get(
                    "cluster_names",
                    {},
                ).items()
            }

            if self.pipeline is None:
                self.load_error = (
                    "The segmentation artifact does not "
                    "contain a prediction pipeline."
                )

        except Exception as error:
            self.pipeline = None
            self.load_error = str(error)

    def predict_segment(
        self,
        features: dict,
    ) -> dict:
        if self.pipeline is None:
            return {
                "success": False,
                "model_loaded": False,
                "cluster": None,
                "segment_name": "UNAVAILABLE",
                "error": (
                    self.load_error
                    or "Segmentation model unavailable."
                ),
                "model_role": (
                    "supporting_dashboard_analytics"
                ),
                "used_in_live_intervention_loop": False,
            }

        try:
            sample_data = {
                column: features.get(column, 0)
                for column in self.feature_columns
            }

            sample = pd.DataFrame(
                [sample_data],
                columns=self.feature_columns,
            )

            cluster = int(
                self.pipeline.predict(sample)[0]
            )

            segment_name = self.cluster_names.get(
                cluster,
                f"Behavior Cluster {cluster}",
            )

            return {
                "success": True,
                "model_loaded": True,
                "model_role": (
                    "supporting_dashboard_analytics"
                ),
                "used_in_live_intervention_loop": False,
                "analytics_purpose": (
                    "Provides an experimental behavioural "
                    "grouping for dashboard awareness. "
                    "It does not control live interventions."
                ),
                "cluster": cluster,
                "segment_name": segment_name,
            }

        except Exception as error:
            return {
                "success": False,
                "model_loaded": True,
                "cluster": None,
                "segment_name": "UNAVAILABLE",
                "error": (
                    "Segment prediction failed: "
                    f"{error}"
                ),
                "model_role": (
                    "supporting_dashboard_analytics"
                ),
                "used_in_live_intervention_loop": False,
            }


segment_service = SegmentService()