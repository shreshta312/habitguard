import math
from typing import Dict, Any, Optional
from app.core.config import SYSTEM_PARAMETERS, SOURCE_VERSIONED_DEFAULT

class UtilityEstimator:
    """
    Estimates necessary usage and task-completion utility U(x).
    Protects necessary tasks without equating purpose with satisfaction.
    """
    def __init__(self):
        cfg = SYSTEM_PARAMETERS["utility_parameters"]["value"]
        self.necessity_w = cfg["necessity_weight"]
        self.completion_w = cfg["completion_weight"]
        self.penalty_w = cfg["under_allocation_penalty"]
        self.min_required_u = cfg["minimum_required_utility"]
        self.typical_sufficient_def = cfg["typical_sufficient_duration_default"]

    def estimate(
        self,
        purpose: str,
        planned_minutes: Optional[float],
        contextual_baseline: float,
        learned_sufficient_duration: Optional[float] = None,
        task_not_finished_count: int = 0
    ) -> Dict[str, Any]:

        # Calculate necessary minimum duration
        sufficient_dur = learned_sufficient_duration or planned_minutes or contextual_baseline or self.typical_sufficient_def
        
        # Task not finished history increases protected minimum time
        task_protection_boost = min(15.0, task_not_finished_count * 5.0)
        necessary_minimum = round(min(sufficient_dur + task_protection_boost, 180.0), 2)

        if purpose in {"work_study", "necessary"}:
            necessity_scale = 1.0
        elif purpose == "entertainment":
            necessity_scale = 0.3
        else:
            necessity_scale = 0.1

        return {
            "necessary_minimum": necessary_minimum,
            "necessity_scale": necessity_scale,
            "typical_sufficient_duration": sufficient_dur,
            "minimum_required_utility": self.min_required_u,
            "parameter_sources": {
                "necessity_weight": SOURCE_VERSIONED_DEFAULT,
                "completion_weight": SOURCE_VERSIONED_DEFAULT
            }
        }

    def predict_completion_probability(self, x: float, typical_sufficient: float) -> float:
        """
        Bounded completion probability C_hat(x) = min(1.0, x / (typical_sufficient + 1e-5)).
        """
        if typical_sufficient <= 0:
            return 1.0
        return min(1.0, max(0.0, x / typical_sufficient))

    def calculate_utility(
        self,
        x: float,
        planned_minutes: Optional[float],
        necessary_minimum: float,
        necessity_scale: float
    ) -> float:
        """
        U(x) = necessity_scale * log(1 + x) + completion_weight * C_hat(x) - penalty * max(0, planned - x)^2
        """
        c_hat = self.predict_completion_probability(x, necessary_minimum)
        term1 = self.necessity_w * necessity_scale * math.log(1.0 + x)
        term2 = self.completion_w * c_hat
        
        if planned_minutes and x < planned_minutes:
            penalty = self.penalty_w * math.pow((planned_minutes - x) / (planned_minutes + 1e-5), 2)
        else:
            penalty = 0.0

        raw_u = term1 + term2 - penalty
        return max(0.0, round(raw_u, 4))
