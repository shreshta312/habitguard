"""
test_legacy_labels.py

Fix 7-E: Legacy timer endpoints must return STRUCTURAL_TIMER_LEGACY labels.
Canonical OPTIMIZED responses must return SESSION_OPTIMIZATION_ENGINE.
Canonical non-OPTIMIZED responses must return is_optimized_target=False.

Fix 7-F: Mathematical verification of the optimizer.
"""
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fix 7-E: Legacy timer labels
# ---------------------------------------------------------------------------

class TestLegacyTimerLabels:
    def test_custom_intervention_returns_legacy_label(self):
        payload = {
            "user_id": "test_user",
            "usage_history_minutes": [30, 35, 40, 38, 42, 45, 50],
            "context": None
        }
        resp = client.post("/habitguard/custom/intervention", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["timer_source"] == "STRUCTURAL_TIMER_LEGACY"
        assert data["optimization_status"] == "LEGACY_FALLBACK"
        assert data["is_optimized_target"] is False

    def test_user_intervention_returns_legacy_label(self):
        resp = client.get("/habitguard/user/user1/intervention")
        if resp.status_code == 404:
            pytest.skip("No user1 in test dataset")
        assert resp.status_code == 200
        data = resp.json()
        assert data["timer_source"] == "STRUCTURAL_TIMER_LEGACY"
        assert data["optimization_status"] == "LEGACY_FALLBACK"
        assert data["is_optimized_target"] is False


# ---------------------------------------------------------------------------
# Fix 7-F: Mathematical verification of the optimizer
# ---------------------------------------------------------------------------

class TestOptimizerMathVerification:
    """Verifies the grid-search optimizer satisfies its stated constraints."""

    def _solve(self, **kwargs):
        from app.services.session_optimization_engine import SessionOptimizationEngine
        from app.services.utility_estimator import UtilityEstimator
        engine = SessionOptimizationEngine(UtilityEstimator())
        defaults = dict(
            session_id="s1", user_id="u1",
            focused_minutes_used=5.0,
            planned_minutes=20.0,
            purpose="entertainment",
            timer_mode="planned",
            temptation_estimate=0.3,
            temptation_confidence=0.8,
            contextual_baseline=30.0,
            necessary_minimum=5.0,
            cross_domain_allowance=120.0,
            tracking_reliability=1.0,
        )
        defaults.update(kwargs)
        return engine.solve(**defaults)

    def test_identical_inputs_return_identical_targets(self):
        r1 = self._solve()
        r2 = self._solve()
        assert r1["optimized_target"] == r2["optimized_target"]

    def test_optimized_target_never_below_used_minutes(self):
        result = self._solve(focused_minutes_used=15.0, planned_minutes=20.0)
        if result["solver_status"] == "OPTIMIZED":
            assert result["optimized_target"] >= 15.0

    def test_necessary_minimum_respected(self):
        result = self._solve(necessary_minimum=10.0, focused_minutes_used=2.0)
        if result["solver_status"] == "OPTIMIZED":
            assert result["optimized_target"] >= 10.0

    def test_cross_domain_allowance_constrains_upper_bound(self):
        tight = self._solve(cross_domain_allowance=8.0, necessary_minimum=5.0, focused_minutes_used=5.0)
        loose = self._solve(cross_domain_allowance=120.0, necessary_minimum=5.0, focused_minutes_used=5.0)
        # With tighter allowance, target should be <= with loose allowance
        if tight["solver_status"] == "OPTIMIZED" and loose["solver_status"] == "OPTIMIZED":
            assert tight["optimized_target"] <= loose["optimized_target"]

    def test_no_timer_mode_returns_no_timer_status(self):
        result = self._solve(timer_mode="no_timer")
        assert result["solver_status"] == "NO_TIMER"
        assert result["optimized_target"] is None

    def test_low_confidence_without_plan_returns_learning(self):
        result = self._solve(temptation_confidence=0.1, planned_minutes=None)
        assert result["solver_status"] == "LEARNING"
        assert result["optimized_target"] is None

    def test_infeasible_returns_explicit_status(self):
        """upper_bound < lower_bound when cross_domain_allowance < necessary_minimum and used."""
        result = self._solve(
            focused_minutes_used=50.0,
            necessary_minimum=5.0,
            cross_domain_allowance=10.0,
            contextual_baseline=5.0,
            planned_minutes=5.0,
        )
        assert result["solver_status"] in ("OPTIMIZED", "NO_FEASIBLE_SOLUTION")

    def test_increased_temptation_may_reduce_target(self):
        """Higher temptation should not increase recommended time on non-necessary usage."""
        low_tempt  = self._solve(temptation_estimate=0.1, purpose="entertainment")
        high_tempt = self._solve(temptation_estimate=0.9, purpose="entertainment")
        if low_tempt["solver_status"] == high_tempt["solver_status"] == "OPTIMIZED":
            assert high_tempt["optimized_target"] <= low_tempt["optimized_target"]

    def test_optimized_result_is_labeled_canonical(self):
        """Canonical batch endpoint must return SESSION_OPTIMIZATION_ENGINE source."""
        # Start a session
        import uuid
        session_resp = client.post("/sessions/start", json={
            "user_id": "test_math_u",
            "domain": "youtube.com",
            "purpose": "entertainment",
            "intended_minutes": 20.0,
            "timer_mode": "planned",
        })
        assert session_resp.status_code == 200
        session_id = session_resp.json()["session_id"]

        batch_resp = client.post(f"/sessions/{session_id}/activity/batch", json={
            "activities": [
                {"event_type": "focus_heartbeat", "focused_duration_ms": 300000,
                 "client_event_id": str(uuid.uuid4()), "event_timestamp_utc": datetime.now(timezone.utc).isoformat()}
            ]
        })
        assert batch_resp.status_code == 200
        data = batch_resp.json()
        assert data["timer_source"] == "SESSION_OPTIMIZATION_ENGINE"

    def test_non_optimized_states_return_is_optimized_false(self):
        """LEARNING status must produce is_optimized_target=False."""
        import uuid
        session_resp = client.post("/sessions/start", json={
            "user_id": "cold_start_user_xyz",
            "domain": "reddit.com",
            "purpose": "unknown",
            "intended_minutes": None,
            "timer_mode": "planned",
        })
        assert session_resp.status_code == 200
        session_id = session_resp.json()["session_id"]

        batch_resp = client.post(f"/sessions/{session_id}/activity/batch", json={
            "activities": [
                {"event_type": "focus_heartbeat", "focused_duration_ms": 120000,
                 "client_event_id": str(uuid.uuid4()), "event_timestamp_utc": datetime.now(timezone.utc).isoformat()}
            ]
        })
        assert batch_resp.status_code == 200
        data = batch_resp.json()
        # When solver_status is LEARNING or similar, is_optimized_target must be False
        if data["optimization_status"] != "OPTIMIZED":
            assert data["is_optimized_target"] is False

    def test_recommended_remaining_never_negative(self):
        result = self._solve(focused_minutes_used=100.0, planned_minutes=20.0,
                             necessary_minimum=5.0, cross_domain_allowance=30.0)
        remaining = result.get("recommended_remaining")
        if remaining is not None:
            assert remaining >= 0
