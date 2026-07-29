"""
cross_domain_goal_service.py  —  Fix 2 (personalized allowance) + Fix 3 (site substitution)

All detection thresholds live in SYSTEM_PARAMETERS["cross_domain_parameters"] so they
have a single versioned home and are exposed on the research route.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

from app.db.repositories.rollups import DailyUsageRollupsRepository
from app.db.repositories.goals import GoalsRepository
from app.core.config import (
    SYSTEM_PARAMETERS, CONFIG_VERSION,
    SOURCE_VERSIONED_DEFAULT, SOURCE_PERSONALLY_LEARNED,
)

# ---------------------------------------------------------------------------
# Pull centralised thresholds once at import time
# ---------------------------------------------------------------------------
_P: Dict[str, Any] = SYSTEM_PARAMETERS.get("cross_domain_parameters", {}).get("value", {})
MEANINGFUL_CHANGE_MINUTES: float = float(_P.get("meaningful_change_minutes", 10.0))
SUBSTITUTION_OFFSET_THRESHOLD: float = float(_P.get("substitution_offset_threshold", 0.50))
MIN_DAYS_FOR_DETECTION: int = int(_P.get("min_days_for_detection", 7))
COLD_START_ALLOWANCE_MINUTES: float = float(_P.get("cold_start_allowance_minutes", 120.0))
SAFETY_FLOOR_MINUTES: float = float(_P.get("safety_floor_minutes", 15.0))
DEFAULT_REDUCTION_PERCENT: float = float(_P.get("default_reduction_percent", 20.0))
MIN_SAMPLES_FOR_LEARNED: int = int(_P.get("min_samples_for_learned", 5))
EPSILON: float = 1e-5


class CrossDomainGoalService:
    """
    Two responsibilities:

    1.  Compute a per-session cross-domain distracting-usage *allowance* from:
          - User's stated reduction goal   (USER_SELECTED)
          - Calibrated personal baseline   (PERSONALLY_LEARNED after >= 5 samples)
          - Necessary / protected minutes  (excluded — never counted as distracting)
          - Usage already consumed today
          - Evidence confidence

    2.  Detect site substitution using two consecutive periods of equal length.
        Returns DETECTED / NOT_DETECTED / INSUFFICIENT_DATA with full evidence.

    Unknown-intention usage is NOT automatically counted as unplanned usage.
    """

    def __init__(
        self,
        rollups_repo: Optional[DailyUsageRollupsRepository] = None,
        goals_repo: Optional[GoalsRepository] = None,
    ) -> None:
        self.repo = rollups_repo or DailyUsageRollupsRepository()
        self.goals_repo = goals_repo or GoalsRepository()

    # ------------------------------------------------------------------
    # Primary public interface (called by the canonical pipeline)
    # ------------------------------------------------------------------

    def get_cross_domain_context(
        self,
        user_id: str,
        current_domain: str,
        days: int = 7,
        focused_minutes_used_today: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Returns the full context dict consumed by SessionOptimizationEngine
        and exposed verbatim on the research route.
        """
        rollups = self.repo.get_user_rollups(user_id, days=days)

        # Aggregate across the window
        total_focused   = sum(float(r.get("focused_minutes",   0)) for r in rollups)
        total_planned   = sum(float(r.get("planned_minutes",   0)) for r in rollups)
        total_unplanned = sum(float(r.get("unplanned_minutes", 0)) for r in rollups)
        total_unknown   = sum(float(r.get("unknown_minutes",   0)) for r in rollups)
        total_necessary = sum(float(r.get("necessary_minutes", 0)) for r in rollups)
        sample_count    = len(rollups)

        # Fetch user's reduction goal
        goal = self.goals_repo.get_goal(user_id) if self.goals_repo else None
        reduction_pct: float = float(
            goal.get("target_reduction_percent", DEFAULT_REDUCTION_PERCENT)
        ) if goal else DEFAULT_REDUCTION_PERCENT
        selected_domains: List[str] = (goal.get("selected_domains") or []) if goal else []

        allowance_result = self._compute_allowance(
            total_focused=total_focused,
            total_necessary=total_necessary,
            reduction_pct=reduction_pct,
            sample_count=sample_count,
            focused_minutes_used_today=focused_minutes_used_today,
        )

        substitution = self._detect_substitution(
            user_id=user_id,
            selected_domains=selected_domains,
            days=days,
        )

        # Domain-level breakdown for research route
        domain_totals: Dict[str, float] = {}
        for r in rollups:
            d = r["domain"]
            domain_totals[d] = round(domain_totals.get(d, 0.0) + float(r.get("focused_minutes", 0)), 2)

        # Personalised goal (distracting only)
        days_estimate = max(1, sample_count // 3)
        avg_daily_focused = total_focused / days_estimate
        personalized_goal_minutes = round(
            avg_daily_focused * (1.0 - reduction_pct / 100.0) * days, 2
        )
        remaining_goal_minutes = round(max(0.0, personalized_goal_minutes - total_focused), 2)

        return {
            # Usage breakdown
            "total_distracting_minutes":  round(total_focused,   2),
            "planned_minutes":            round(total_planned,   2),
            "unplanned_minutes":          round(total_unplanned, 2),
            "unknown_minutes":            round(total_unknown,   2),
            "necessary_minutes":          round(total_necessary, 2),
            # Goal
            "personalized_goal_minutes":  personalized_goal_minutes,
            "remaining_goal_minutes":     remaining_goal_minutes,
            # Allowance (passed into optimizer)
            "cross_domain_allowance_minutes":      allowance_result["value"],
            "allowance_source":                    allowance_result["source"],
            "allowance_confidence":                allowance_result["confidence"],
            "allowance_sample_count":              sample_count,
            "allowance_configuration_version":     CONFIG_VERSION,
            # Substitution
            "site_substitution_status":  substitution["status"],
            "substitution_evidence":     substitution.get("evidence", {}),
            # Domain detail
            "domain_breakdown":          domain_totals,
            # Top-level provenance (mirrors allowance for convenience)
            "parameter_source":          allowance_result["source"],
            "confidence":                allowance_result["confidence"],
            "sample_count":              sample_count,
        }

    # ------------------------------------------------------------------
    # Allowance calculation  (Fix 2)
    # ------------------------------------------------------------------

    def _compute_allowance(
        self,
        total_focused: float,
        total_necessary: float,
        reduction_pct: float,
        sample_count: int,
        focused_minutes_used_today: float,
    ) -> Dict[str, Any]:
        """
        Rules:
        - Necessary/protected usage is excluded from the distracting budget.
        - Unknown usage is NOT automatically unplanned.
        - Cold start (< MIN_SAMPLES_FOR_LEARNED rows) → VERSIONED_DEFAULT.
        - Calibrated → derive target from personal baseline → PERSONALLY_LEARNED.
        - Result is always >= SAFETY_FLOOR_MINUTES.
        """
        if sample_count < MIN_SAMPLES_FOR_LEARNED:
            raw = max(0.0, COLD_START_ALLOWANCE_MINUTES - focused_minutes_used_today)
            return {
                "value":      round(raw, 2),
                "source":     SOURCE_VERSIONED_DEFAULT,
                "confidence": round(min(0.2, sample_count / MIN_SAMPLES_FOR_LEARNED * 0.2), 3),
            }

        # Distracting baseline excludes protected minutes
        distracting_baseline = max(0.0, total_focused - total_necessary)
        days_est = max(1, sample_count // 3)
        avg_daily = distracting_baseline / days_est

        # Target = baseline * (1 - reduction%) minus what's already used today
        target_daily = avg_daily * (1.0 - reduction_pct / 100.0)
        raw = max(0.0, target_daily - focused_minutes_used_today)

        # Confidence grows with evidence; saturates at 1.0 at 20 samples
        confidence = round(min(1.0, sample_count / 20.0), 3)
        source = (
            SOURCE_PERSONALLY_LEARNED
            if sample_count >= MIN_SAMPLES_FOR_LEARNED
            else SOURCE_VERSIONED_DEFAULT
        )

        return {
            "value":      round(raw, 2),
            "source":     source,
            "confidence": confidence,
        }

    # ------------------------------------------------------------------
    # Site-substitution detection  (Fix 3)
    # ------------------------------------------------------------------

    def _detect_substitution(
        self,
        user_id: str,
        selected_domains: List[str],
        days: int,
    ) -> Dict[str, Any]:
        """
        Compares two consecutive periods of length `days`.

        Necessary-minutes are excluded from per-domain totals so that
        protected study/work usage never triggers a false flag.

        Returns:
            status: DETECTED | NOT_DETECTED | INSUFFICIENT_DATA
        """
        # Fetch double window to get two periods
        all_rollups = self.repo.get_user_rollups(user_id, days=days * 2 + 4)
        today = datetime.now(timezone.utc).date()
        current_start = today - timedelta(days=days)
        reference_start = current_start - timedelta(days=days)

        curr_totals: Dict[str, float] = {}
        ref_totals:  Dict[str, float] = {}
        curr_rows = 0
        ref_rows  = 0

        for r in all_rollups:
            try:
                row_date = datetime.fromisoformat(str(r["local_date"])).date()
            except (ValueError, TypeError):
                continue

            domain = r["domain"]
            focused   = float(r.get("focused_minutes",   0.0))
            necessary = float(r.get("necessary_minutes", 0.0))
            distracting = max(0.0, focused - necessary)

            if current_start <= row_date <= today:
                curr_totals[domain] = curr_totals.get(domain, 0.0) + distracting
                curr_rows += 1
            elif reference_start <= row_date < current_start:
                ref_totals[domain] = ref_totals.get(domain, 0.0) + distracting
                ref_rows += 1

        if curr_rows < MIN_DAYS_FOR_DETECTION or ref_rows < MIN_DAYS_FOR_DETECTION:
            return {
                "status": "INSUFFICIENT_DATA",
                "evidence": {
                    "current_rows":  curr_rows,
                    "reference_rows": ref_rows,
                    "required_rows": MIN_DAYS_FOR_DETECTION,
                },
            }

        # Only monitored (selected) domains can trigger a decrease flag
        monitored: set = set(selected_domains) if selected_domains else set(curr_totals.keys())
        decreased: List[Dict[str, Any]] = []
        increased: List[Dict[str, Any]] = []

        for d in monitored | set(ref_totals.keys()):
            curr_min = curr_totals.get(d, 0.0)
            ref_min  = ref_totals.get(d, 0.0)
            change   = curr_min - ref_min

            if change <= -MEANINGFUL_CHANGE_MINUTES and d in monitored:
                decreased.append({"domain": d, "change_minutes": round(change, 2)})
            elif change >= MEANINGFUL_CHANGE_MINUTES:
                increased.append({"domain": d, "change_minutes": round(change, 2)})

        if not decreased or not increased:
            return {
                "status": "NOT_DETECTED",
                "evidence": {
                    "decreased_domains": decreased,
                    "increased_domains": increased,
                },
            }

        total_decrease = abs(sum(d["change_minutes"] for d in decreased))
        total_increase = sum(d["change_minutes"] for d in increased)
        offset_ratio   = round(total_increase / max(total_decrease, EPSILON), 3)

        if offset_ratio < SUBSTITUTION_OFFSET_THRESHOLD:
            return {
                "status": "NOT_DETECTED",
                "evidence": {
                    "decreased_domains":        decreased,
                    "increased_domains":        increased,
                    "offset_ratio":             offset_ratio,
                    "required_offset_threshold": SUBSTITUTION_OFFSET_THRESHOLD,
                },
            }

        return {
            "status": "DETECTED",
            "evidence": {
                "decreased_domains":  decreased,
                "increased_domains":  increased,
                "offset_ratio":       offset_ratio,
                "confidence":         round(min(1.0, offset_ratio), 3),
                "periods": {
                    "reference": f"{reference_start.isoformat()} to {current_start.isoformat()}",
                    "current":   f"{current_start.isoformat()} to {today.isoformat()}",
                },
                "threshold_source":           SOURCE_VERSIONED_DEFAULT,
                "meaningful_change_minutes":  MEANINGFUL_CHANGE_MINUTES,
                "offset_threshold":           SUBSTITUTION_OFFSET_THRESHOLD,
                "configuration_version":      CONFIG_VERSION,
            },
        }
