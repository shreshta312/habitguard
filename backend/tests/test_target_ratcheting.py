"""
test_target_ratcheting.py

Deterministic tests verifying optimization target bounds, monotonic lower-bound enforcement
with increasing focused_minutes_used, and upper bound constraints across consecutive evaluations.
"""
import pytest
from app.services.session_optimization_engine import SessionOptimizationEngine
from app.services.utility_estimator import UtilityEstimator


@pytest.fixture
def optimizer():
    return SessionOptimizationEngine(UtilityEstimator())


def test_target_does_not_shrink_below_focused_minutes_used(optimizer):
    """
    As focused_minutes_used increases within a session, lower_bound enforces that
    the optimized target is never lower than the minutes already used.
    """
    base_kwargs = dict(
        session_id="sess_ratchet_1",
        user_id="user_ratchet",
        planned_minutes=30.0,
        purpose="entertainment",
        timer_mode="planned",
        temptation_estimate=0.8,  # High temptation
        temptation_confidence=0.9,
        contextual_baseline=30.0,
        necessary_minimum=10.0,
        cross_domain_allowance=120.0,
    )

    # Initial run at 10 mins used
    res1 = optimizer.solve(focused_minutes_used=10.0, **base_kwargs)
    assert res1["solver_status"] == "OPTIMIZED"
    target1 = res1["optimized_target"]
    assert target1 >= 10.0

    # Consecutive run as usage increases to 25 mins
    res2 = optimizer.solve(focused_minutes_used=25.0, **base_kwargs)
    assert res2["solver_status"] == "OPTIMIZED"
    target2 = res2["optimized_target"]
    assert target2 >= 25.0

    # Consecutive run when usage exceeds planned target (e.g. 40 mins used)
    res3 = optimizer.solve(focused_minutes_used=40.0, **base_kwargs)
    assert res3["solver_status"] == "OPTIMIZED"
    target3 = res3["optimized_target"]
    assert target3 == 40.0, f"Expected target to retain used minutes 40.0, got {target3}"


def test_user_extension_increases_upper_bound_and_target(optimizer):
    """
    User-requested extensions increase effective_planned_minutes, which relaxes
    the upper bound and permits a higher optimized target.
    """
    base_kwargs = dict(
        session_id="sess_ratchet_ext",
        user_id="user_ratchet",
        focused_minutes_used=20.0,
        purpose="work_study",
        timer_mode="planned",
        temptation_estimate=0.3,
        temptation_confidence=0.9,
        contextual_baseline=30.0,
        necessary_minimum=15.0,
        cross_domain_allowance=120.0,
    )

    # Original planned: 20 mins
    res_orig = optimizer.solve(planned_minutes=20.0, **base_kwargs)
    target_orig = res_orig["optimized_target"]

    # Extended planned: 20 + 15 = 35 mins
    res_ext = optimizer.solve(planned_minutes=35.0, **base_kwargs)
    target_ext = res_ext["optimized_target"]

    assert target_ext >= target_orig, (
        f"Expected extended target ({target_ext}) to be >= original target ({target_orig})"
    )


def test_cross_domain_allowance_caps_upper_bound(optimizer):
    """
    Cross-domain allowance acts as a ceiling constraint on upper_bound.
    """
    res = optimizer.solve(
        session_id="sess_ratchet_cd",
        user_id="user_ratchet",
        focused_minutes_used=10.0,
        planned_minutes=60.0,
        purpose="entertainment",
        timer_mode="planned",
        temptation_estimate=0.1,
        temptation_confidence=0.9,
        contextual_baseline=60.0,
        necessary_minimum=10.0,
        cross_domain_allowance=25.0,  # Strict cross-domain cap
    )

    assert res["solver_status"] == "OPTIMIZED"
    assert res["optimized_target"] <= 25.0, (
        f"Expected target to be capped by cross-domain allowance 25.0, got {res['optimized_target']}"
    )
