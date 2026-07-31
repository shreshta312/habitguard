from typing import Dict, Any
from app.core.config import SYSTEM_PARAMETERS, SOURCE_VERSIONED_DEFAULT

def clamp(val: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    return max(min_val, min(max_val, val))

class TemptationEstimator:
    """
    Computes an internal, bounded behavioral estimate T in [0, 1].
    Temptation is an internal estimate, not a directly observed fact.
    """
    def __init__(self, custom_weights: Dict[str, float] | None = None):
        cfg = SYSTEM_PARAMETERS["temptation_weights"]["value"]
        self.weights = custom_weights or cfg

    def estimate(self, features: Dict[str, Any], purpose: str = "unknown") -> Dict[str, Any]:
        O = float(features.get("plan_overrun_ratio", 0.0))
        R = float(features.get("reopen_frequency", 0.0))
        L = float(features.get("longest_uninterrupted_usage", 0.0))
        
        # Unknown purpose is NEVER treated as habitual browsing
        if purpose == "habitual_browsing":
            H = 1.0
        else:
            H = 0.0

        K = float(features.get("context_signal", 0.5))
        W = float(features.get("rapid_switching", 0.0))
        Q = float(features.get("historical_overrun_rate", 0.0))

        w1 = self.weights.get("w1_overrun", 0.25)
        w2 = self.weights.get("w2_reopen", 0.15)
        w3 = self.weights.get("w3_uninterrupted", 0.15)
        w4 = self.weights.get("w4_habitual", 0.20)
        w5 = self.weights.get("w5_context", 0.10)
        w6 = self.weights.get("w6_switching", 0.10)
        w7 = self.weights.get("w7_historical_overrun", 0.05)

        T_raw = w1*O + w2*R + w3*L + w4*H + w5*K + w6*W + w7*Q
        T_bounded = clamp(T_raw, 0.0, 1.0)

        # Blend in the habit stock normalized value if present (Allcott paper connection)
        habit_stock_norm = float(features.get("habit_stock", 0.0))
        T_blended = clamp(0.85 * T_bounded + 0.15 * habit_stock_norm, 0.0, 1.0)

        # Missing intention or tracking unreliability lowers confidence
        tracking_rel = float(features.get("tracking_reliability", 1.0))
        missing_plan = 1 if features.get("plan_overrun_minutes") is None else 0
        
        confidence = 0.9 * tracking_rel
        if purpose == "unknown" or missing_plan:
            confidence *= 0.7

        missing_signals = []
        if purpose == "unknown":
            missing_signals.append("user_declared_purpose")
        if features.get("plan_overrun_minutes") is None:
            missing_signals.append("planned_duration")

        return {
            "temptation_estimate": round(T_blended, 4),
            "confidence": round(confidence, 4),
            "component_values": {
                "overrun_term": round(w1 * O, 4),
                "reopen_term": round(w2 * R, 4),
                "uninterrupted_term": round(w3 * L, 4),
                "habitual_term": round(w4 * H, 4),
                "context_term": round(w5 * K, 4),
                "switching_term": round(w6 * W, 4),
                "historical_overrun_term": round(w7 * Q, 4)
            },
            "evidence": {
                "plan_overrun_ratio": O,
                "reopen_frequency": R,
                "uninterrupted_usage": L,
                "purpose": purpose
            },
            "missing_signals": missing_signals,
            "estimator_version": "2.0.0",
            "parameter_source": SOURCE_VERSIONED_DEFAULT
        }
