"""
personal_adaptation_service.py  —  Fix 4 (complete feedback-to-adaptation wiring)

Rules:
- Called by FeedbackService AFTER persistence succeeds.
- Never updates structural parameters (rho_user, eta, zeta, gamma).
- Every update uses EMA with a configurable learning rate.
- One event cannot radically change a parameter (learning_rate capped at 0.25).
- Parameters are contextual: keyed by (user_id, domain, purpose) where relevant.
- Full trace is stored per update.
"""
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from app.db.repositories.parameters import PersonalParametersRepository
from app.core.config import (
    SYSTEM_PARAMETERS, CONFIG_VERSION,
    SOURCE_PERSONALLY_LEARNED, SOURCE_VERSIONED_DEFAULT,
)

_LR_CFG = SYSTEM_PARAMETERS.get("learning_rates", {}).get("value", {})
DEFAULT_ETA: float = float(_LR_CFG.get("default_learning_rate", 0.15))
MIN_SAMPLE_FOR_LEARNED: int = int(_LR_CFG.get("min_sample_count_for_learned", 5))
MAX_ETA: float = 0.25          # hard cap — one event cannot radically shift a parameter
PARTIAL_ETA_FACTOR: float = 0.5  # used for partly_completed / partly_sufficient


class PersonalAdaptationService:
    """
    Interprets validated, persisted feedback events and gradually updates
    contextual personal parameters via EMA:

        theta_next = (1 - eta) * theta_curr + eta * observation

    Parameter taxonomy:
    - learned_sufficient_duration  : domain-level, updated by task/time feedback
    - acceptance_rate              : global, updated by dismiss / finish / extend_5
    - task_not_finished_count      : domain-level, monotonically incremented
    - stop_reminders_episode       : episode-scoped boolean flag

    Structural parameters (rho_user, eta, zeta, gamma) are NOT touched here.
    """

    def __init__(self, params_repo: Optional[PersonalParametersRepository] = None) -> None:
        self.repo = params_repo or PersonalParametersRepository()

    def process_feedback_event(
        self,
        event: Dict[str, Any],
        session_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Route the persisted event to the correct adaptation rule.

        Returns an adaptation_trace dict that FeedbackService stores
        and the research route exposes.
        """
        ctx = session_context or {}
        user_id = event.get("user_id", "local_user")
        action  = event.get("action", "")

        # Normalise the structured fields (may come from API or persisted event)
        task_completion  = event.get("task_completion",  ctx.get("task_completion"))
        time_sufficient  = event.get("time_sufficient",  ctx.get("time_sufficient"))
        actual_focused   = float(ctx.get("actual_focused_minutes", 0.0) or 0.0)
        planned_minutes  = float(ctx.get("planned_minutes", 0.0) or 0.0)
        optimized_target = float(ctx.get("optimized_target", 0.0) or 0.0)
        domain           = ctx.get("domain", "unknown")
        purpose          = ctx.get("purpose", "unknown")

        trace: Dict[str, Any] = {
            "user_id":    user_id,
            "action":     action,
            "domain":     domain,
            "purpose":    purpose,
            "timestamp":  datetime.now(timezone.utc).isoformat(),
            "updates":    [],
        }

        # ----------------------------------------------------------------
        # A. Insufficient time / task not finished
        # ----------------------------------------------------------------
        if (
            action == "task_not_finished"
            or task_completion == "not_completed"
            or time_sufficient == "insufficient"
        ):
            # Increment task_not_finished_count (monotonic counter)
            count_key = f"task_not_finished_count_{domain}"
            current_count = self.repo.get_parameter(user_id, count_key)
            new_count = (int(current_count["value"]) + 1) if current_count else 1
            self.repo.set_parameter(
                user_id=user_id,
                parameter_name=count_key,
                value=new_count,
                source=SOURCE_PERSONALLY_LEARNED,
                confidence=round(min(1.0, new_count / 5.0), 3),
                sample_count=new_count,
            )
            trace["updates"].append({"param": count_key, "new_value": new_count})

            # Update learned_sufficient_duration upward ONLY if purpose is work_study or necessary
            if purpose in {"work_study", "necessary"}:
                observed_req = max(actual_focused, planned_minutes, optimized_target)
                if observed_req > 0:
                    dur_key = f"learned_sufficient_duration_{domain}_{purpose}"
                    current_dur = self.repo.get_parameter(user_id, dur_key)
                    curr_val = float(current_dur["value"]) if current_dur else observed_req
                    sample_count = (current_dur["sample_count"] + 1) if current_dur else 1
                    eta = min(MAX_ETA, DEFAULT_ETA)
                    # Enforce bounded EMA and max per-event increase (+15 min max)
                    obs_bounded = min(observed_req, curr_val + 15.0)
                    new_val = round(max(5.0, min(180.0, (1 - eta) * curr_val + eta * obs_bounded)), 2)
                    self.repo.set_parameter(
                        user_id=user_id,
                        parameter_name=dur_key,
                        value=new_val,
                        source=SOURCE_PERSONALLY_LEARNED,
                        confidence=round(min(1.0, sample_count / 10.0), 3),
                        sample_count=sample_count,
                    )
                    trace["updates"].append({
                        "param": dur_key,
                        "prev_value": curr_val,
                        "new_value": new_val,
                        "observation": obs_bounded,
                        "eta": eta,
                        "direction": "upward",
                    })

        # ----------------------------------------------------------------
        # B. Completed and sufficient — update toward actual duration
        # ----------------------------------------------------------------
        elif task_completion == "completed" and time_sufficient == "sufficient":
            observed_suf = actual_focused
            if observed_suf > 0:
                dur_key = f"learned_sufficient_duration_{domain}_{purpose}"
                current_dur = self.repo.get_parameter(user_id, dur_key)
                curr_val = float(current_dur["value"]) if current_dur else observed_suf
                sample_count = (current_dur["sample_count"] + 1) if current_dur else 1
                eta = min(MAX_ETA, DEFAULT_ETA)
                new_val = round((1 - eta) * curr_val + eta * observed_suf, 2)
                self.repo.set_parameter(
                    user_id=user_id,
                    parameter_name=dur_key,
                    value=new_val,
                    source=SOURCE_PERSONALLY_LEARNED,
                    confidence=round(min(1.0, sample_count / 10.0), 3),
                    sample_count=sample_count,
                )
                trace["updates"].append({
                    "param": dur_key,
                    "prev_value": curr_val,
                    "new_value": new_val,
                    "observation": observed_suf,
                    "eta": eta,
                    "direction": "toward_actual",
                })

        # ----------------------------------------------------------------
        # C. Sufficient without task-completion info — weak evidence only
        # ----------------------------------------------------------------
        elif time_sufficient == "sufficient" and task_completion in (None, "unknown"):
            dur_key = f"learned_sufficient_duration_{domain}_{purpose}"
            current_dur = self.repo.get_parameter(user_id, dur_key)
            if current_dur:
                new_count = current_dur["sample_count"] + 1
                self.repo.set_parameter(
                    user_id=user_id,
                    parameter_name=dur_key,
                    value=current_dur["value"],   # value unchanged
                    source=current_dur["source"],
                    confidence=round(min(1.0, new_count / 10.0), 3),
                    sample_count=new_count,
                )
                trace["updates"].append({
                    "param": dur_key,
                    "note": "confidence_increment_only",
                    "sample_count": new_count,
                })

        # ----------------------------------------------------------------
        # D. Partly completed / partly sufficient — small learning rate
        # ----------------------------------------------------------------
        elif task_completion == "partly_completed" or time_sufficient == "partly_sufficient":
            observed_req = max(actual_focused, planned_minutes, optimized_target)
            if observed_req > 0:
                dur_key = f"learned_sufficient_duration_{domain}_{purpose}"
                current_dur = self.repo.get_parameter(user_id, dur_key)
                curr_val = float(current_dur["value"]) if current_dur else observed_req
                sample_count = (current_dur["sample_count"] + 1) if current_dur else 1
                eta = min(MAX_ETA, DEFAULT_ETA * PARTIAL_ETA_FACTOR)
                new_val = round((1 - eta) * curr_val + eta * observed_req, 2)
                self.repo.set_parameter(
                    user_id=user_id,
                    parameter_name=dur_key,
                    value=new_val,
                    source=SOURCE_PERSONALLY_LEARNED,
                    confidence=round(min(1.0, sample_count / 10.0), 3),
                    sample_count=sample_count,
                )
                trace["updates"].append({
                    "param": dur_key,
                    "prev_value": curr_val,
                    "new_value": new_val,
                    "eta": eta,
                    "note": "partial_update",
                })

        # ----------------------------------------------------------------
        # E. Dismiss — update intervention receptivity only
        # ----------------------------------------------------------------
        if action == "dismiss":
            self._update_acceptance_rate(user_id, obs_val=0.0, trace=trace)

        # ----------------------------------------------------------------
        # F. Extend 5 — conscious extension (not dismissal)
        # ----------------------------------------------------------------
        elif action == "extend_5":
            self._update_acceptance_rate(user_id, obs_val=1.0, trace=trace, note="extend")

        # ----------------------------------------------------------------
        # G. Finish — potential successful stopping
        # ----------------------------------------------------------------
        elif action == "finish":
            self._update_acceptance_rate(user_id, obs_val=1.0, trace=trace, note="finish")

        # ----------------------------------------------------------------
        # H. Stop reminders — episode-scoped flag only
        # ----------------------------------------------------------------
        elif action == "stop_reminders":
            episode_key = f"stop_reminders_episode_{event.get('session_id', 'unknown')}"
            self.repo.set_parameter(
                user_id=user_id,
                parameter_name=episode_key,
                value=1,
                source=SOURCE_PERSONALLY_LEARNED,
                confidence=1.0,
                sample_count=1,
            )
            trace["updates"].append({"param": episode_key, "new_value": 1, "scope": "episode"})

        return trace

    # ------------------------------------------------------------------
    # Internal helper — EMA update on acceptance_rate
    # ------------------------------------------------------------------

    def _update_acceptance_rate(
        self,
        user_id: str,
        obs_val: float,
        trace: Dict[str, Any],
        note: str = "",
    ) -> None:
        param_name = "acceptance_rate"
        current = self.repo.get_parameter(user_id, param_name)
        curr_val     = float(current["value"])     if current else 0.5
        sample_count = (current["sample_count"] + 1) if current else 1
        eta = min(MAX_ETA, DEFAULT_ETA)
        new_val = round((1 - eta) * curr_val + eta * obs_val, 4)
        self.repo.set_parameter(
            user_id=user_id,
            parameter_name=param_name,
            value=new_val,
            source=SOURCE_PERSONALLY_LEARNED,
            confidence=round(min(1.0, sample_count / 10.0), 3),
            sample_count=sample_count,
        )
        trace["updates"].append({
            "param":        param_name,
            "prev_value":   curr_val,
            "new_value":    new_val,
            "observation":  obs_val,
            "eta":          eta,
            "sample_count": sample_count,
            **({"note": note} if note else {}),
        })
