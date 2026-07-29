from typing import Dict, Any, List

def clamp(val: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    return max(min_val, min(max_val, val))

class BehaviorFeatureService:
    """
    Calculates normalized behavioral signals strictly in [0, 1].
    """
    def extract_features(
        self,
        focused_minutes: float,
        planned_minutes: float | None,
        purpose: str,
        reopen_count: int = 0,
        uninterrupted_minutes: float = 0.0,
        cross_domain_switches: int = 0,
        historical_overrun_rate: float = 0.0,
        feedback_summary: Dict[str, Any] | None = None
    ) -> Dict[str, float]:

        # Plan overrun ratio normalized
        if planned_minutes and planned_minutes > 0:
            overrun_minutes = max(0.0, focused_minutes - planned_minutes)
            overrun_ratio = clamp(overrun_minutes / (planned_minutes + 1e-5))
        else:
            overrun_minutes = 0.0
            overrun_ratio = 0.0

        # Reopen frequency normalized (scale: 10 reopens = 1.0)
        reopen_norm = clamp(reopen_count / 10.0)

        # Uninterrupted usage normalized (scale: 60 mins = 1.0)
        uninterrupted_norm = clamp(uninterrupted_minutes / 60.0)

        # Habitual browsing indicator
        habitual_indicator = 1.0 if purpose == "habitual_browsing" else 0.0

        # Rapid switching normalized (scale: 15 switches = 1.0)
        switching_norm = clamp(cross_domain_switches / 15.0)

        # Context signal (default neutral 0.5)
        context_signal = 0.5

        # Historical overrun rate clamp
        hist_overrun_norm = clamp(historical_overrun_rate)

        # Severity estimate in [0, 1]
        severity = clamp(
            0.4 * overrun_ratio +
            0.2 * reopen_norm +
            0.2 * uninterrupted_norm +
            0.2 * habitual_indicator
        )

        fb = feedback_summary or {}
        acceptance_rate = float(fb.get("acceptance_rate", 0.5))

        return {
            "focused_session_minutes": round(focused_minutes, 2),
            "plan_overrun_minutes": round(overrun_minutes, 2),
            "plan_overrun_ratio": round(overrun_ratio, 4),
            "reopen_frequency": round(reopen_norm, 4),
            "longest_uninterrupted_usage": round(uninterrupted_norm, 4),
            "habitual_indicator": habitual_indicator,
            "rapid_switching": round(switching_norm, 4),
            "context_signal": context_signal,
            "historical_overrun_rate": round(hist_overrun_norm, 4),
            "severity": round(severity, 4),
            "acceptance_rate": round(acceptance_rate, 4),
            "tracking_reliability": 1.0
        }
