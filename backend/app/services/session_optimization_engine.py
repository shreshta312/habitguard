import math
from typing import Dict, Any, List, Optional
from app.core.config import SYSTEM_PARAMETERS, CONFIG_VERSION, SOURCE_VERSIONED_DEFAULT, SOURCE_USER_SELECTED, SOURCE_PERSONALLY_LEARNED
from app.services.utility_estimator import UtilityEstimator

class SessionOptimizationEngine:
    """
    Deterministic grid-search constrained solver evaluating candidate total focused duration x.
    Never uses a hardcoded 10/17-minute clamp.
    """
    def __init__(self, utility_estimator: Optional[UtilityEstimator] = None):
        self.utility_estimator = utility_estimator or UtilityEstimator()
        cfg = SYSTEM_PARAMETERS["optimization_coefficients"]["value"]
        self.alpha = cfg["alpha_usage_cost"]
        self.beta = cfg["beta_temptation_cost"]
        self.lambda_dev = cfg["lambda_plan_deviation"]
        # Reference parameters from theoretical formulation (handled via binding constraints and policy)
        self.kappa_burden_reference = cfg["kappa_intervention_burden"]
        self.gamma_goal_reference = cfg["gamma_reduction_goal"]
        self.session_scale = cfg["session_scale_minutes"]
        self.grid_step = cfg["grid_search_step_minutes"]
        self.safe_max_default = cfg["safe_session_maximum_minutes"]

    def solve(
        self,
        session_id: str,
        user_id: str,
        focused_minutes_used: float,
        planned_minutes: Optional[float],
        purpose: str,
        timer_mode: str,
        temptation_estimate: float,
        temptation_confidence: float,
        contextual_baseline: float,
        necessary_minimum: float,
        cross_domain_allowance: float = 180.0,
        prompt_burden: float = 0.0,
        tracking_reliability: float = 1.0,
        stop_reminders: bool = False,
        user_override: Optional[float] = None
    ) -> Dict[str, Any]:

        input_snapshot = {
            "session_id": session_id,
            "user_id": user_id,
            "focused_minutes_used": focused_minutes_used,
            "planned_minutes": planned_minutes,
            "purpose": purpose,
            "timer_mode": timer_mode,
            "temptation_estimate": temptation_estimate,
            "temptation_confidence": temptation_confidence,
            "contextual_baseline": contextual_baseline,
            "necessary_minimum": necessary_minimum,
            "cross_domain_allowance": cross_domain_allowance,
            "prompt_burden": prompt_burden,
            "tracking_reliability": tracking_reliability,
            "stop_reminders": stop_reminders,
            "user_override": user_override
        }

        # Handle explicit override / no_timer / tracking unreliability
        if timer_mode == "no_timer":
            return self._build_result(input_snapshot, status="NO_TIMER", target=None)

        if stop_reminders:
            return self._build_result(input_snapshot, status="USER_OVERRIDE", target=None)

        if tracking_reliability < 0.5:
            return self._build_result(input_snapshot, status="TRACKING_UNRELIABLE", target=None)

        if user_override is not None:
            remaining = max(0.0, round(user_override - focused_minutes_used, 2))
            return self._build_result(input_snapshot, status="USER_OVERRIDE", target=user_override, remaining=remaining)

        # Cold start handling (low confidence & sample count)
        if temptation_confidence < 0.2 and (planned_minutes is None or planned_minutes == 0):
            return self._build_result(input_snapshot, status="LEARNING", target=None)

        # Contextual upper bound calculation
        plan_ref = planned_minutes if planned_minutes and planned_minutes > 0 else contextual_baseline
        contextual_upper_bound = round(max(necessary_minimum, plan_ref + 15.0), 2)

        # Compute candidate bounds
        lower_bound = max(0.0, focused_minutes_used, necessary_minimum)
        upper_bound = min(self.safe_max_default, contextual_upper_bound, cross_domain_allowance)

        # Check feasibility of bounds
        if upper_bound < lower_bound:
            # Usage is beyond feasible target
            if focused_minutes_used >= necessary_minimum:
                return self._build_result(
                    input_snapshot,
                    status="OPTIMIZED",
                    target=focused_minutes_used,
                    remaining=0.0,
                    obj_val=0.0,
                    binding_constraints=["upper_bound_exceeded_used_retained"]
                )
            else:
                return self._build_result(input_snapshot, status="NO_FEASIBLE_SOLUTION", target=None)

        # Grid search solver
        best_x = None
        best_obj = float("inf")
        best_utility = 0.0
        feasible_count = 0

        curr_x = lower_bound
        while curr_x <= upper_bound + 1e-5:
            # Check utility constraint
            necessity_scale = 1.0 if purpose in {"work_study", "necessary"} else 0.3
            u_x = self.utility_estimator.calculate_utility(
                x=curr_x,
                planned_minutes=planned_minutes,
                necessary_minimum=necessary_minimum,
                necessity_scale=necessity_scale
            )

            min_required_u = self.utility_estimator.min_required_u
            if u_x >= min_required_u:
                feasible_count += 1
                # Calculate objective J(x)
                usage_cost = curr_x / self.session_scale
                
                if planned_minutes and planned_minutes > 0:
                    plan_dev = math.pow((curr_x - planned_minutes) / (planned_minutes + 1e-5), 2)
                else:
                    plan_dev = math.pow((curr_x - contextual_baseline) / (contextual_baseline + 1e-5), 2)

                J = (
                    self.alpha * usage_cost +
                    self.beta * temptation_estimate * usage_cost +
                    self.lambda_dev * plan_dev
                )

                if J < best_obj:
                    best_obj = J
                    best_x = curr_x
                    best_utility = u_x

            curr_x += self.grid_step

        if best_x is None:
            return self._build_result(input_snapshot, status="NO_FEASIBLE_SOLUTION", target=None)

        best_x = round(best_x, 2)
        remaining = max(0.0, round(best_x - focused_minutes_used, 2))

        binding = []
        if abs(best_x - focused_minutes_used) < 1e-3:
            binding.append("already_used_lower_bound")
        if abs(best_x - necessary_minimum) < 1e-3:
            binding.append("necessary_minimum_lower_bound")
        if abs(best_x - contextual_upper_bound) < 1e-3:
            binding.append("contextual_upper_bound")
        if abs(best_x - cross_domain_allowance) < 1e-3:
            binding.append("cross_domain_upper_bound")
        if abs(best_utility - self.utility_estimator.min_required_u) < 1e-3:
            binding.append("utility_minimum")

        best_usage_cost = best_x / self.session_scale
        if planned_minutes and planned_minutes > 0:
            best_plan_dev = math.pow((best_x - planned_minutes) / (planned_minutes + 1e-5), 2)
        else:
            best_plan_dev = math.pow((best_x - contextual_baseline) / (contextual_baseline + 1e-5), 2)

        comp_usage = round(self.alpha * best_usage_cost, 4)
        comp_temptation = round(self.beta * temptation_estimate * best_usage_cost, 4)
        comp_plan_dev = round(self.lambda_dev * best_plan_dev, 4)
        comp_goal_dev = 0.0  # Reduction goal enforced via binding constraint x <= cross_domain_allowance

        return self._build_result(
            input_snapshot,
            status="OPTIMIZED",
            target=best_x,
            remaining=remaining,
            obj_val=round(best_obj, 4),
            utility=round(best_utility, 4),
            binding_constraints=binding,
            derivation={
                "optimized_total_candidate": best_x,
                "recommended_additional_minutes": remaining,
                "candidate_lower_bound": lower_bound,
                "candidate_upper_bound": upper_bound,
                "grid_evaluations": int((upper_bound - lower_bound) / self.grid_step) + 1,
                "feasible_candidates": feasible_count,
                "contextual_upper_bound": contextual_upper_bound,
                "temptation_estimate": temptation_estimate,
                "utility_min": self.utility_estimator.min_required_u,
                "utility_min_source": SOURCE_VERSIONED_DEFAULT,
                "beta": self.beta,
                "temptation_cost": comp_temptation,
                "objective_components": {
                    "usage_cost_contribution": comp_usage,
                    "temptation_cost_contribution": comp_temptation,
                    "plan_deviation_contribution": comp_plan_dev,
                    "goal_deviation_contribution": comp_goal_dev
                },
                "selected_objective_value": round(best_obj, 4),
                "parameter_sources": {
                    "alpha": SOURCE_VERSIONED_DEFAULT,
                    "beta": SOURCE_VERSIONED_DEFAULT,
                    "lambda": SOURCE_VERSIONED_DEFAULT,
                    "gamma": SOURCE_VERSIONED_DEFAULT,
                    "utility_min": SOURCE_VERSIONED_DEFAULT
                }
            }
        )

    def _build_result(
        self,
        snapshot: Dict[str, Any],
        status: str,
        target: Optional[float],
        remaining: Optional[float] = None,
        obj_val: Optional[float] = None,
        utility: Optional[float] = None,
        binding_constraints: Optional[List[str]] = None,
        derivation: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        opt_target = target
        rec_additional = remaining if remaining is not None else (max(0.0, target - snapshot["focused_minutes_used"]) if target else None)
        return {
            "session_id": snapshot["session_id"],
            "user_id": snapshot["user_id"],
            "solver_status": status,
            "optimized_target": opt_target,
            "optimized_total_candidate": opt_target,
            "recommended_remaining": rec_additional,
            "recommended_additional_minutes": rec_additional,
            "objective_value": obj_val,
            "utility_retained": utility,
            "utility_min": self.utility_estimator.min_required_u,
            "utility_min_source": SOURCE_VERSIONED_DEFAULT,
            "constraints_satisfied": status in {"OPTIMIZED", "USER_OVERRIDE"},
            "binding_constraints": binding_constraints or [],
            "derivation": derivation or {},
            "input_snapshot": snapshot,
            "observed_baseline": snapshot["contextual_baseline"],
            "baseline_source": "CONTEXTUAL_BASELINE_FALLBACK",
            "necessary_minimum": snapshot["necessary_minimum"],
            "minutes_used": snapshot["focused_minutes_used"],
            "temptation_estimate": snapshot["temptation_estimate"],
            "temptation_confidence": snapshot["temptation_confidence"],
            "tracking_reliability": snapshot["tracking_reliability"],
            "configuration_version": CONFIG_VERSION,
            "parameter_sources": {
                "alpha": SOURCE_VERSIONED_DEFAULT,
                "beta": SOURCE_VERSIONED_DEFAULT,
                "lambda": SOURCE_VERSIONED_DEFAULT,
                "utility_min": SOURCE_VERSIONED_DEFAULT
            }
        }
