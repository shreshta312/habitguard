class DecisionEngine:
    """
    Combines the structural timer output with live Chrome context.

    StructuralTimerEngine answers:
        "What does the user's usage pattern suggest?"

    DecisionEngine answers:
        "Given the current context, should HabitGuard intervene,
         and what kind of intervention should it show?"
    """

    def __init__(self):
        pass

    def decide(self, timer_result, context=None):
        context = context or {}

        if timer_result.get("mode") == "CALIBRATION":
            return {
                "mode": "CALIBRATION",
                "timer_active": False,
                "usage_status": "COLLECTING_BASELINE",
                "friction_type": "NONE",
                "recommended_timer_minutes": None,
                "intervention_type": "NONE",
                "should_intervene": False,
                "decision_reason": "HabitGuard is still collecting baseline data.",
                "message": timer_result.get("message")
            }

        overuse_gap = timer_result.get("overuse_gap_minutes", 0) or 0
        recommended_timer = round(timer_result.get("recommended_timer_minutes", 0))

        current_domain = context.get("current_domain")
        current_category = context.get("current_category") or "neutral"
        session_minutes = context.get("session_minutes") or 0

        usage_status, friction_type, message = self._base_decision_from_overuse(
            overuse_gap
        )

        intervention_type = self._intervention_type_from_friction(friction_type)
        should_intervene = friction_type != "NONE"

        decision_reason = (
            f"Base decision from overuse gap: {overuse_gap} min."
        )

        # Productive context should reduce unnecessary interruptions.
        if current_category == "productive":
            if friction_type in ("TIMER_WARNING", "STRONG_FRICTION"):
                friction_type = "SOFT_WARNING"
                usage_status = "PRODUCTIVE_CONTEXT"
                intervention_type = "GENTLE_CHECKIN"
                should_intervene = True
                message = (
                    "You're above your usual usage, but this site is marked productive. "
                    "HabitGuard will keep the intervention gentle."
                )
                decision_reason = (
                    f"Productive site context reduced friction for {current_domain}."
                )
            elif friction_type == "SOFT_WARNING":
                friction_type = "NONE"
                usage_status = "STABLE_PRODUCTIVE"
                intervention_type = "NONE"
                should_intervene = False
                message = (
                    "Usage is slightly above baseline, but the current site is productive. "
                    "No intervention needed right now."
                )
                decision_reason = (
                    f"Productive site context suppressed soft warning for {current_domain}."
                )

        # Temptation context should increase urgency when the current session is long.
        elif current_category == "temptation" and session_minutes >= 10:
            if friction_type == "NONE":
                usage_status = "TEMPTATION_SESSION"
                friction_type = "SOFT_WARNING"
                intervention_type = "REFLECTION_PROMPT"
                should_intervene = True
                message = (
                    "You've been on a temptation site for a while. "
                    "Pause and check whether this is intentional."
                )
                decision_reason = (
                    f"Temptation site session reached {session_minutes} minutes."
                )

            elif friction_type == "SOFT_WARNING":
                usage_status = "TEMPTATION_OVERUSE"
                friction_type = "TIMER_WARNING"
                intervention_type = "TIMER_NUDGE"
                should_intervene = True
                message = (
                    "This temptation-site session is going beyond your usual pattern. "
                    "A timer is recommended."
                )
                decision_reason = (
                    f"Temptation site + overuse gap of {overuse_gap} min."
                )

            elif friction_type == "TIMER_WARNING" and overuse_gap > 20:
                usage_status = "RISKY_TEMPTATION_USAGE"
                friction_type = "STRONG_FRICTION"
                intervention_type = "BREAK_PROMPT"
                should_intervene = True
                message = (
                    "This session is high-risk: temptation site plus strong overuse. "
                    "Take a short break before continuing."
                )
                decision_reason = (
                    f"High overuse gap ({overuse_gap} min) on temptation site."
                )

        return {
            "mode": timer_result.get("mode"),
            "timer_active": timer_result.get("timer_active"),
            "usage_status": usage_status,
            "friction_type": friction_type,
            "recommended_timer_minutes": recommended_timer,
            "overuse_gap_minutes": overuse_gap,
            "baseline_usage_minutes": timer_result.get("baseline_usage_minutes"),
            "recent_usage_minutes": timer_result.get("recent_usage_minutes"),
            "rho_user": timer_result.get("rho_user"),
            "intervention_type": intervention_type,
            "should_intervene": should_intervene,
            "decision_reason": decision_reason,
            "message": message,
            "context_used": {
                "current_domain": current_domain,
                "current_category": current_category,
                "session_minutes": session_minutes
            }
        }

    def _base_decision_from_overuse(self, overuse_gap):
        if overuse_gap == 0:
            return (
                "STABLE",
                "NONE",
                "Your usage is close to your baseline. No intervention needed right now."
            )

        if overuse_gap <= 10:
            return (
                "SLIGHTLY_ABOVE_BASELINE",
                "SOFT_WARNING",
                "Your usage is slightly above your normal pattern. Consider taking a short break."
            )

        if overuse_gap <= 30:
            return (
                "HIGH_USAGE",
                "TIMER_WARNING",
                "Your usage is noticeably above baseline. A timer limit is recommended."
            )

        return (
            "RISKY_USAGE_SPIKE",
            "STRONG_FRICTION",
            "Your usage is much higher than usual. A stricter break or blocking intervention is recommended."
        )

    def _intervention_type_from_friction(self, friction_type):
        if friction_type == "NONE":
            return "NONE"

        if friction_type == "SOFT_WARNING":
            return "GENTLE_CHECKIN"

        if friction_type == "TIMER_WARNING":
            return "TIMER_NUDGE"

        if friction_type == "STRONG_FRICTION":
            return "BREAK_PROMPT"

        return "GENTLE_CHECKIN"