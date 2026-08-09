from typing import Dict, Any, Optional

def clamp(val: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    return max(min_val, min(max_val, val))

class DecisionEngine:
    """
    Consumes optimizer output (or legacy timer_result) and live context to make intervention decisions.
    Supports both canonical optimization results and legacy timer dictionaries for test backward compatibility.
    """
    def __init__(self, min_feedback_events=3, min_cooldown_minutes: float = 15.0):
        self.min_feedback_events = min_feedback_events
        self.min_cooldown_minutes = min_cooldown_minutes

    def decide(
        self,
        timer_result: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        feedback_summary: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        context = context or {}
        fb = feedback_summary or {}

        # Handle Empty History or Calibration
        if timer_result.get("mode") == "NO_DATA":
            return {
                "mode": "NO_DATA",
                "timer_active": False,
                "usage_status": "INSUFFICIENT_DATA",
                "friction_type": "NONE",
                "recommended_timer_minutes": None,
                "overuse_gap_minutes": 0,
                "baseline_usage_minutes": 0,
                "recent_usage_minutes": 0,
                "rho_user": 0,
                "intervention_type": "NONE",
                "should_intervene": False,
                "decision_reason": "No usage history available.",
                "message": "Start browsing to establish baseline.",
                "context_used": context,
                "feedback_adaptation_used": False,
                "feedback_adaptation_reason": "No feedback adaptation applied.",
                "error": timer_result.get("error", "No usage history available")
            }

        if timer_result.get("mode") == "CALIBRATION":
            return {
                "mode": "CALIBRATION",
                "timer_active": False,
                "usage_status": "COLLECTING_BASELINE",
                "friction_type": "NONE",
                "recommended_timer_minutes": None,
                "overuse_gap_minutes": 0,
                "baseline_usage_minutes": timer_result.get("baseline_usage_minutes", 0),
                "recent_usage_minutes": timer_result.get("recent_usage_minutes", 0),
                "rho_user": timer_result.get("rho_user", 0.3),
                "intervention_type": "NONE",
                "should_intervene": False,
                "decision_reason": "HabitGuard is still collecting baseline data.",
                "message": timer_result.get("message"),
                "context_used": context,
                "feedback_adaptation_used": False,
                "feedback_adaptation_reason": "Calibration mode active."
            }

        current_domain = context.get("current_domain")
        current_category = context.get("current_category", "neutral")
        session_minutes = context.get("session_minutes", 0)
        planned_minutes = context.get("planned_minutes") if context.get("planned_minutes") is not None else timer_result.get("planned_minutes")

        # Determine session_status with robust float boundary logic
        if planned_minutes is None or planned_minutes <= 0:
            session_status = "NO_PLAN"
        elif session_minutes > planned_minutes:
            session_status = "OVER_PLAN"
        elif (planned_minutes - session_minutes <= 2.0 and (planned_minutes - session_minutes) / planned_minutes <= 0.25) or abs(session_minutes - planned_minutes) <= 0.1:
            session_status = "NEAR_PLAN"
        else:
            session_status = "WITHIN_PLAN"

        overuse_gap = timer_result.get("overuse_gap_minutes", 0) or 0
        recommended_timer = timer_result.get("recommended_timer_minutes") or timer_result.get("optimized_target")

        usage_status, friction_type, message = self._base_decision_from_overuse(overuse_gap)

        feedback_adaptation_used = False
        feedback_adaptation_reason = "No feedback adaptation applied."
        suppression_reason = None

        # Evaluate receptivity & prompt burden from feedback summary (do not permanently suppress)
        high_prompt_burden = False
        if fb and current_domain and fb.get("most_dismissed_sites"):
            for site, count in fb.get("most_dismissed_sites", []):
                if site.lower() == current_domain.lower() and count >= 3:
                    high_prompt_burden = True

        # Check global low acceptance adaptation
        if fb and fb.get("total_events", 0) >= self.min_feedback_events:
            acceptance_rate = fb.get("break_acceptance_rate", fb.get("acceptance_rate", 0.5))
            if acceptance_rate < 0.2 and friction_type == "STRONG_FRICTION":
                friction_type = "TIMER_WARNING"
                feedback_adaptation_used = True
                feedback_adaptation_reason = "Softened friction due to low past feedback acceptance rate."

        # Context overrides (productive vs temptation)
        if current_category == "productive":
            if friction_type in ("TIMER_WARNING", "STRONG_FRICTION"):
                friction_type = "SOFT_WARNING"
                usage_status = "PRODUCTIVE_CONTEXT"
                intervention_type = "GENTLE_CHECKIN"
                should_intervene = True
                message = "You're above your usual usage, but this site is marked productive. HabitGuard will keep the intervention gentle."
            elif friction_type == "SOFT_WARNING":
                friction_type = "NONE"
                usage_status = "STABLE_PRODUCTIVE"
                intervention_type = "NONE"
                should_intervene = False
                message = "Usage is slightly above baseline, but the current site is productive. No intervention needed right now."
            else:
                should_intervene = False
                intervention_type = "NONE"
        elif current_category == "temptation" and session_minutes >= 10:
            if friction_type == "NONE":
                usage_status = "TEMPTATION_SESSION"
                friction_type = "SOFT_WARNING"
                intervention_type = "REFLECTION_PROMPT"
                should_intervene = True
                message = "You've been on a temptation site for a while. Pause and check whether this is intentional."
            elif friction_type == "SOFT_WARNING":
                usage_status = "TEMPTATION_OVERUSE"
                friction_type = "TIMER_WARNING"
                intervention_type = "TIMER_NUDGE"
                should_intervene = True
                message = "This temptation-site session is going beyond your usual pattern. A timer is recommended."
            elif overuse_gap >= 15:
                usage_status = "RISKY_TEMPTATION_USAGE"
                friction_type = "STRONG_FRICTION"
                intervention_type = "ACTIVE_BLOCK"
                should_intervene = True
                message = "Heavy overuse on a temptation site."
            else:
                intervention_type = self._intervention_type_from_friction(friction_type)
                should_intervene = True
        else:
            intervention_type = self._intervention_type_from_friction(friction_type)
            should_intervene = friction_type != "NONE"

        # OVER_PLAN message override & suppression_reason logic
        if session_status == "OVER_PLAN":
            overrun = round(session_minutes - planned_minutes, 2)
            overrun_fmt = int(overrun) if (overrun == int(overrun)) else overrun
            overrun_msg = f"Over plan. {overrun_fmt} min over."
            if (message == "Usage is within normal limits." or "Over plan" not in message) and current_category != "productive":
                message = overrun_msg
            if not should_intervene:
                if timer_result.get("solver_status") == "LEARNING" or timer_result.get("confidence", 1.0) < 0.2:
                    suppression_reason = "low_confidence"
                elif overrun < 2.0:
                    suppression_reason = "small_absolute_overrun"
                elif current_category == "productive":
                    suppression_reason = "productive_context"
                elif timer_result.get("cooldown_active"):
                    suppression_reason = "cooldown"
                else:
                    suppression_reason = "baseline_allowance"

        if timer_result.get("cooldown_active"):
            should_intervene = False
            suppression_reason = "cooldown"
            friction_type = "NONE"
            message = "Intervention suppressed due to active cooldown."

        policy_score = clamp(0.5 * (overuse_gap / 30.0) + 0.5) if should_intervene else 0.0

        import uuid
        decision_id = f"dec_{uuid.uuid4().hex[:12]}"
        should_notify = should_intervene and friction_type in ("SOFT_WARNING", "TIMER_WARNING")
        should_overlay = should_intervene and friction_type in ("TIMER_WARNING", "STRONG_FRICTION")

        severity_level = "NONE"
        if friction_type == "SOFT_WARNING":
            severity_level = "LOW"
        elif friction_type == "TIMER_WARNING":
            severity_level = "MEDIUM"
        elif friction_type == "STRONG_FRICTION":
            severity_level = "HIGH"

        receptivity_state = "HIGH" if not high_prompt_burden else "BURDENED"

        return {
            "decision_id": decision_id,
            "mode": timer_result.get("mode", "ACTIVE"),
            "timer_active": timer_result.get("timer_active", True),
            "session_status": session_status,
            "suppression_reason": suppression_reason,
            "usage_status": usage_status,
            "friction_type": friction_type,
            "severity": severity_level,
            "receptivity_state": receptivity_state,
            "recommended_timer_minutes": recommended_timer,
            "overuse_gap_minutes": overuse_gap,
            "baseline_usage_minutes": timer_result.get("observed_baseline", timer_result.get("baseline_usage_minutes", 0)),
            "recent_usage_minutes": timer_result.get("minutes_used", timer_result.get("recent_usage_minutes", 0)),
            "rho_user": timer_result.get("rho_user", 0.3),
            "intervention_type": intervention_type,
            "should_intervene": should_intervene,
            "should_notify": should_notify,
            "should_overlay": should_overlay,
            "cooldown_channel": "notification" if should_notify else ("overlay" if should_overlay else "none"),
            "cooldown_source": "VERSIONED_DEFAULT",
            "last_delivered_timestamp": context.get("last_delivered_timestamp"),
            "next_eligible_timestamp": context.get("next_eligible_timestamp"),
            "policy_score": round(policy_score, 4),
            "message": message,
            "decision_reason": f"Base decision from overuse gap: {overuse_gap} min.",
            "context_used": {
                "current_domain": current_domain,
                "current_category": current_category,
                "session_minutes": session_minutes,
                "planned_minutes": planned_minutes
            },
            "feedback_adaptation_used": feedback_adaptation_used,
            "feedback_adaptation_reason": feedback_adaptation_reason
        }

    def _base_decision_from_overuse(self, overuse_gap: float):
        if overuse_gap <= 0:
            return "STABLE", "NONE", "Usage is within normal limits."
        elif overuse_gap < 15:
            return "SLIGHT_OVERUSE", "SOFT_WARNING", f"You have exceeded your baseline by {overuse_gap} minutes."
        elif overuse_gap < 30:
            return "MODERATE_OVERUSE", "TIMER_WARNING", f"You have exceeded your baseline by {overuse_gap} minutes."
        else:
            return "HEAVY_OVERUSE", "STRONG_FRICTION", f"You are significantly over your baseline ({overuse_gap} minutes)."

    def _intervention_type_from_friction(self, friction_type: str):
        if friction_type == "SOFT_WARNING":
            return "REFLECTION_PROMPT"
        elif friction_type == "TIMER_WARNING":
            return "TIMER_NUDGE"
        elif friction_type == "STRONG_FRICTION":
            return "ACTIVE_BLOCK"
        return "NONE"