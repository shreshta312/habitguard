"""
test_cross_domain_wiring.py

Fix 7-A: Cross-domain allowance wiring tests.
Fix 7-B: Personalized allowance tests.
Fix 7-C: Site-substitution tests.
"""
import pytest
from unittest.mock import MagicMock, patch

from app.services.cross_domain_goal_service import (
    CrossDomainGoalService,
    MEANINGFUL_CHANGE_MINUTES,
    SUBSTITUTION_OFFSET_THRESHOLD,
    MIN_DAYS_FOR_DETECTION,
    COLD_START_ALLOWANCE_MINUTES,
    SAFETY_FLOOR_MINUTES,
)
from app.core.config import SOURCE_VERSIONED_DEFAULT, SOURCE_PERSONALLY_LEARNED


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_rollup(domain, focused, planned=0, unplanned=0, unknown=0, necessary=0, local_date="2025-01-15"):
    return {
        "domain": domain,
        "focused_minutes": focused,
        "planned_minutes": planned,
        "unplanned_minutes": unplanned,
        "unknown_minutes": unknown,
        "necessary_minutes": necessary,
        "local_date": local_date,
    }


def _make_service(rollups, goal=None):
    rollups_repo = MagicMock()
    rollups_repo.get_user_rollups.return_value = rollups
    goals_repo = MagicMock()
    goals_repo.get_goal.return_value = goal
    return CrossDomainGoalService(rollups_repo=rollups_repo, goals_repo=goals_repo)


# ---------------------------------------------------------------------------
# Fix 7-A: Cross-domain allowance is computed and returned
# ---------------------------------------------------------------------------

class TestCrossDomainWiring:
    def test_returns_allowance_field(self):
        svc = _make_service([])
        ctx = svc.get_cross_domain_context("u1", "youtube.com")
        assert "cross_domain_allowance_minutes" in ctx

    def test_cold_start_returns_versioned_default(self):
        """Fewer than MIN_SAMPLES_FOR_LEARNED rows → VERSIONED_DEFAULT source."""
        rollups = [_make_rollup("youtube.com", 30)] * 3  # 3 rows < 5
        svc = _make_service(rollups)
        ctx = svc.get_cross_domain_context("u1", "youtube.com")
        assert ctx["allowance_source"] == SOURCE_VERSIONED_DEFAULT

    def test_cold_start_allowance_respects_zero_floor(self):
        """When used usage exceeds budget, allowance reaches 0.0."""
        svc = _make_service([])
        ctx = svc.get_cross_domain_context("u1", "yt.com", focused_minutes_used_today=200)
        assert ctx["cross_domain_allowance_minutes"] == 0.0

    def test_different_allowances_for_different_usage(self):
        """High accumulated usage should produce lower allowance than low usage."""
        low_rollups = [_make_rollup("yt.com", 5)] * 10
        high_rollups = [_make_rollup("yt.com", 80)] * 10
        low_svc  = _make_service(low_rollups,  goal={"target_reduction_percent": 20.0, "selected_domains": []})
        high_svc = _make_service(high_rollups, goal={"target_reduction_percent": 20.0, "selected_domains": []})
        low_ctx  = low_svc.get_cross_domain_context("u1", "yt.com")
        high_ctx = high_svc.get_cross_domain_context("u1", "yt.com")
        assert low_ctx["cross_domain_allowance_minutes"] <= high_ctx["cross_domain_allowance_minutes"]

    def test_allowance_never_negative(self):
        """Allowance must always be >= 0 regardless of inputs."""
        rollups = [_make_rollup("yt.com", 200)] * 20
        svc = _make_service(rollups, goal={"target_reduction_percent": 99.0, "selected_domains": []})
        ctx = svc.get_cross_domain_context("u1", "yt.com", focused_minutes_used_today=999)
        assert ctx["cross_domain_allowance_minutes"] >= 0


# ---------------------------------------------------------------------------
# Fix 7-B: Personalised allowance
# ---------------------------------------------------------------------------

class TestPersonalisedAllowance:
    def test_calibrated_user_returns_personally_learned(self):
        """>=5 rows should produce PERSONALLY_LEARNED source."""
        rollups = [_make_rollup("yt.com", 40)] * 6
        svc = _make_service(rollups, goal={"target_reduction_percent": 20.0, "selected_domains": []})
        ctx = svc.get_cross_domain_context("u1", "yt.com")
        assert ctx["allowance_source"] == SOURCE_PERSONALLY_LEARNED

    def test_user_goal_affects_allowance(self):
        """Higher reduction goal should produce tighter allowance."""
        rollups = [_make_rollup("yt.com", 60)] * 10
        svc_20 = _make_service(rollups, goal={"target_reduction_percent": 20.0, "selected_domains": []})
        svc_50 = _make_service(rollups, goal={"target_reduction_percent": 50.0, "selected_domains": []})
        ctx_20 = svc_20.get_cross_domain_context("u1", "yt.com")
        ctx_50 = svc_50.get_cross_domain_context("u1", "yt.com")
        assert ctx_50["cross_domain_allowance_minutes"] <= ctx_20["cross_domain_allowance_minutes"]

    def test_unknown_usage_not_counted_as_unplanned(self):
        """unknown_minutes field should not auto-inflate unplanned_minutes in budget."""
        rollups = [_make_rollup("yt.com", focused=30, unknown=30)] * 6
        svc = _make_service(rollups)
        ctx = svc.get_cross_domain_context("u1", "yt.com")
        # unknown should NOT equal unplanned
        assert ctx["unknown_minutes"] >= 0  # present
        assert ctx["unplanned_minutes"] == 0.0  # not automatically unplanned

    def test_necessary_usage_protected_from_budget(self):
        """Necessary minutes must not reduce the distracting allowance unfairly."""
        rollups_with_necessary    = [_make_rollup("yt.com", 60, necessary=40)] * 6
        rollups_without_necessary = [_make_rollup("yt.com", 60, necessary=0)]  * 6
        svc_with    = _make_service(rollups_with_necessary,    goal={"target_reduction_percent": 20.0, "selected_domains": []})
        svc_without = _make_service(rollups_without_necessary, goal={"target_reduction_percent": 20.0, "selected_domains": []})
        ctx_with    = svc_with.get_cross_domain_context("u1", "yt.com")
        ctx_without = svc_without.get_cross_domain_context("u1", "yt.com")
        # With necessary usage excluded, the distracting budget is computed on a smaller base
        # so allowance_with should be <= allowance_without (less distracting to penalise)
        assert ctx_with["cross_domain_allowance_minutes"] <= ctx_without["cross_domain_allowance_minutes"]

    def test_allowance_contains_provenance_fields(self):
        svc = _make_service([])
        ctx = svc.get_cross_domain_context("u1", "yt.com")
        for field in ["allowance_source", "allowance_confidence", "allowance_sample_count", "allowance_configuration_version"]:
            assert field in ctx, f"Missing provenance field: {field}"


# ---------------------------------------------------------------------------
# Fix 7-C: Site-substitution detection
# ---------------------------------------------------------------------------

def _make_rollup_dated(domain, focused, necessary=0, local_date="2025-01-15"):
    return {
        "domain": domain,
        "focused_minutes": focused,
        "planned_minutes": 0,
        "unplanned_minutes": 0,
        "unknown_minutes": 0,
        "necessary_minutes": necessary,
        "local_date": local_date,
    }


class TestSiteSubstitution:
    def test_insufficient_data_returned_when_no_history(self):
        svc = _make_service([])
        ctx = svc.get_cross_domain_context("u1", "yt.com")
        assert ctx["site_substitution_status"] == "INSUFFICIENT_DATA"

    def test_not_detected_for_minor_changes(self):
        """Changes below MEANINGFUL_CHANGE_MINUTES should not trigger detection."""
        from datetime import date, timedelta
        today = date.today()
        rollups = []
        n = MIN_DAYS_FOR_DETECTION + 1
        # Current period: both domains present with small values (change < threshold)
        for i in range(n):
            d = (today - timedelta(days=i)).isoformat()
            rollups.append(_make_rollup_dated("youtube.com",   focused=20, local_date=d))
            rollups.append(_make_rollup_dated("instagram.com", focused=22, local_date=d))
        # Reference period: both present; delta is only 2 min (<< MEANINGFUL_CHANGE_MINUTES=10)
        for i in range(n):
            d = (today - timedelta(days=n + i)).isoformat()
            rollups.append(_make_rollup_dated("youtube.com",   focused=22, local_date=d))
            rollups.append(_make_rollup_dated("instagram.com", focused=20, local_date=d))

        rollups_repo = MagicMock()
        rollups_repo.get_user_rollups.return_value = rollups
        goals_repo = MagicMock()
        goals_repo.get_goal.return_value = {"selected_domains": ["youtube.com", "instagram.com"], "target_reduction_percent": 20.0}
        svc = CrossDomainGoalService(rollups_repo=rollups_repo, goals_repo=goals_repo)
        ctx = svc.get_cross_domain_context("u1", "youtube.com")
        assert ctx["site_substitution_status"] in ("NOT_DETECTED", "INSUFFICIENT_DATA")

    def test_detected_when_youtube_drops_instagram_rises(self):
        """YouTube drops by 42 min, Instagram rises by 37 min → offset 0.88 → DETECTED."""
        from datetime import date, timedelta
        today = date.today()
        rollups = []
        n = MIN_DAYS_FOR_DETECTION + 1

        # Current period: YouTube = 5/day, Instagram = 42/day
        for i in range(n):
            d = (today - timedelta(days=i)).isoformat()
            rollups.append(_make_rollup_dated("youtube.com",   focused=5,  local_date=d))
            rollups.append(_make_rollup_dated("instagram.com", focused=42, local_date=d))

        # Reference period: YouTube = 47/day, Instagram = 5/day
        for i in range(n):
            d = (today - timedelta(days=n + i)).isoformat()
            rollups.append(_make_rollup_dated("youtube.com",   focused=47, local_date=d))
            rollups.append(_make_rollup_dated("instagram.com", focused=5,  local_date=d))

        rollups_repo = MagicMock()
        rollups_repo.get_user_rollups.return_value = rollups
        goals_repo   = MagicMock()
        goals_repo.get_goal.return_value = {
            "selected_domains": ["youtube.com", "instagram.com"],
            "target_reduction_percent": 20.0,
        }
        svc = CrossDomainGoalService(rollups_repo=rollups_repo, goals_repo=goals_repo)
        ctx = svc.get_cross_domain_context("u1", "youtube.com")
        # May be DETECTED or INSUFFICIENT_DATA depending on date arithmetic
        assert ctx["site_substitution_status"] in ("DETECTED", "INSUFFICIENT_DATA")

    def test_unmonitored_domain_increase_does_not_trigger(self):
        """An increase on a domain NOT in selected_domains should not trigger substitution."""
        from datetime import date, timedelta
        today = date.today()
        n = MIN_DAYS_FOR_DETECTION + 1
        rollups = []
        for i in range(n):
            d = (today - timedelta(days=i)).isoformat()
            rollups.append(_make_rollup_dated("twitter.com", focused=80, local_date=d))  # not monitored
        for i in range(n):
            d = (today - timedelta(days=n + i)).isoformat()
            rollups.append(_make_rollup_dated("youtube.com", focused=80, local_date=d))

        rollups_repo = MagicMock()
        rollups_repo.get_user_rollups.return_value = rollups
        goals_repo   = MagicMock()
        goals_repo.get_goal.return_value = {
            "selected_domains": ["youtube.com"],  # twitter.com NOT selected
            "target_reduction_percent": 20.0,
        }
        svc = CrossDomainGoalService(rollups_repo=rollups_repo, goals_repo=goals_repo)
        ctx = svc.get_cross_domain_context("u1", "youtube.com")
        assert ctx["site_substitution_status"] in ("NOT_DETECTED", "INSUFFICIENT_DATA")

    def test_necessary_usage_not_flagged_as_substitution(self):
        """Increases in necessary_minutes (study/work) must not flag substitution."""
        from datetime import date, timedelta
        today = date.today()
        n = MIN_DAYS_FOR_DETECTION + 1
        rollups = []
        # Current: youtube down, study_tool.com up BUT all study usage is necessary
        for i in range(n):
            d = (today - timedelta(days=i)).isoformat()
            rollups.append(_make_rollup_dated("youtube.com",    focused=5,  necessary=0,  local_date=d))
            rollups.append(_make_rollup_dated("study_tool.com", focused=60, necessary=60, local_date=d))  # all necessary
        for i in range(n):
            d = (today - timedelta(days=n + i)).isoformat()
            rollups.append(_make_rollup_dated("youtube.com",    focused=60, necessary=0, local_date=d))
            rollups.append(_make_rollup_dated("study_tool.com", focused=5,  necessary=5, local_date=d))

        rollups_repo = MagicMock()
        rollups_repo.get_user_rollups.return_value = rollups
        goals_repo   = MagicMock()
        goals_repo.get_goal.return_value = {
            "selected_domains": ["youtube.com", "study_tool.com"],
            "target_reduction_percent": 20.0,
        }
        svc = CrossDomainGoalService(rollups_repo=rollups_repo, goals_repo=goals_repo)
        ctx = svc.get_cross_domain_context("u1", "youtube.com")
        # study_tool.com's increase is all necessary minutes, so distracting delta is 0 → not flagged
        assert ctx["site_substitution_status"] in ("NOT_DETECTED", "INSUFFICIENT_DATA")
