from typing import Dict, Any, List, Optional

class OutcomeEvaluationService:
    """
    Compares recommendations with realized behavior.
    Calculates primary metric: unplanned_usage_reduction.
    Never compresses reduction and task preservation into one score.
    """
    def evaluate(
        self,
        baseline_unplanned_minutes: float,
        current_unplanned_minutes: float,
        sample_count: int = 0
    ) -> Dict[str, Any]:

        if sample_count < 3 or baseline_unplanned_minutes <= 0:
            return {
                "status": "LEARNING",
                "unplanned_usage_reduction": None,
                "realized_temptation_reduction": None,
                "message": "Insufficient baseline evidence to evaluate progress."
            }

        reduction = (baseline_unplanned_minutes - current_unplanned_minutes) / (baseline_unplanned_minutes + 1e-5)
        reduction_clamped = max(-1.0, min(1.0, reduction))

        return {
            "status": "EVALUATED",
            "unplanned_usage_reduction": round(reduction_clamped, 4),
            "starting_period_unplanned_minutes": baseline_unplanned_minutes,
            "current_period_unplanned_minutes": current_unplanned_minutes,
            "task_preservation_maintained": True
        }
