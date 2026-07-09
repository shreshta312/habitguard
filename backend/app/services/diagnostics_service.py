"""
Model diagnostics service.

Exposes metadata and performance estimates for all loaded ML models.
Nothing here modifies model state — it only reads model attributes
and returns a diagnostic summary.
"""

import pickle
import numpy as np
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parents[3] / "ml" / "saved_models"


def _safe_load(name):
    path = MODELS_DIR / name
    if not path.exists():
        return None
    with open(path, "rb") as f:
        return pickle.load(f)


def _model_type(model):
    if model is None:
        return "not_loaded"
    return type(model).__name__


def _has_attr(model, attr):
    return model is not None and hasattr(model, attr)


def get_diagnostics():
    """
    Returns a dictionary summarising every loaded model,
    plus any stored training metrics we can read from model attributes.
    """

    anomaly_model = _safe_load("anomaly_detector.pkl")
    anomaly_scaler = _safe_load("anomaly_scaler.pkl")
    risk_model = _safe_load("risk_classifier.pkl")
    forecaster_model = _safe_load("usage_forecaster.pkl")
    segment_model = _safe_load("user_segmentation.pkl")

    diagnostics = {
        "models_loaded": {
            "anomaly_detector": anomaly_model is not None,
            "anomaly_scaler": anomaly_scaler is not None,
            "risk_classifier": risk_model is not None,
            "usage_forecaster": forecaster_model is not None,
            "user_segmentation": segment_model is not None,
        },
        "anomaly_detector": _anomaly_diagnostics(anomaly_model, anomaly_scaler),
        "risk_classifier": _risk_diagnostics(risk_model),
        "usage_forecaster": _forecaster_diagnostics(forecaster_model),
        "user_segmentation": _segment_diagnostics(segment_model),
    }

    return diagnostics


def _anomaly_diagnostics(model, scaler):
    info = {
        "model_type": _model_type(model),
        "scaler_type": _model_type(scaler),
    }

    if _has_attr(model, "contamination"):
        info["contamination"] = float(model.contamination)

    if _has_attr(model, "offset_"):
        info["offset"] = float(model.offset_)

    if _has_attr(model, "n_features_in_"):
        info["n_features"] = int(model.n_features_in_)

    if _has_attr(scaler, "mean_"):
        info["scaler_means"] = [round(float(m), 4) for m in scaler.mean_]

    if _has_attr(scaler, "scale_"):
        info["scaler_scales"] = [round(float(s), 4) for s in scaler.scale_]

    return info


def _risk_diagnostics(model):
    info = {
        "model_type": _model_type(model),
    }

    if _has_attr(model, "n_features_in_"):
        info["n_features"] = int(model.n_features_in_)

    if _has_attr(model, "n_classes_"):
        info["n_classes"] = int(model.n_classes_)

    if _has_attr(model, "classes_"):
        info["classes"] = [int(c) for c in model.classes_]

    if _has_attr(model, "n_estimators"):
        info["n_estimators"] = int(model.n_estimators)

    if _has_attr(model, "feature_importances_"):
        importances = model.feature_importances_
        if _has_attr(model, "feature_names_in_"):
            names = list(model.feature_names_in_)
        else:
            names = [f"feature_{i}" for i in range(len(importances))]

        ranked = sorted(
            zip(names, importances),
            key=lambda x: x[1],
            reverse=True,
        )
        info["top_features"] = [
            {"name": n, "importance": round(float(v), 4)} for n, v in ranked[:5]
        ]

    return info


def _forecaster_diagnostics(model):
    info = {
        "model_type": _model_type(model),
    }

    if _has_attr(model, "n_features_in_"):
        info["n_features"] = int(model.n_features_in_)

    if _has_attr(model, "n_estimators"):
        info["n_estimators"] = int(model.n_estimators)

    if _has_attr(model, "feature_names_in_"):
        info["feature_names"] = list(model.feature_names_in_)

    if _has_attr(model, "feature_importances_"):
        importances = model.feature_importances_
        if _has_attr(model, "feature_names_in_"):
            names = list(model.feature_names_in_)
        else:
            names = [f"feature_{i}" for i in range(len(importances))]

        ranked = sorted(
            zip(names, importances),
            key=lambda x: x[1],
            reverse=True,
        )
        info["top_features"] = [
            {"name": n, "importance": round(float(v), 4)} for n, v in ranked
        ]

    return info


def _segment_diagnostics(model):
    info = {
        "model_type": _model_type(model),
    }

    if _has_attr(model, "n_clusters"):
        info["n_clusters"] = int(model.n_clusters)

    if _has_attr(model, "cluster_centers_"):
        centers = model.cluster_centers_
        info["n_cluster_centers"] = len(centers)
        info["cluster_center_norms"] = [
            round(float(np.linalg.norm(c)), 4) for c in centers
        ]

    if _has_attr(model, "inertia_"):
        info["inertia"] = round(float(model.inertia_), 4)

    if _has_attr(model, "n_iter_"):
        info["n_iterations"] = int(model.n_iter_)

    return info
