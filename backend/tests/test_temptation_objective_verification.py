"""
test_temptation_objective_verification.py

Targeted verification tests for SessionOptimizationEngine temptation objective component.
"""
import pytest
from app.services.session_optimization_engine import SessionOptimizationEngine
from app.services.utility_estimator import UtilityEstimator
from app.core.config import SOURCE_VERSIONED_DEFAULT


@pytest.fixture
def optimizer():
    return SessionOptimizationEngine(UtilityEstimator())


def test_higher_temptation_produces_strictly_lower_target_when_non_binding(optimizer):
    """
    Test 1: With all other inputs equal and utility non-binding,
    a higher temptation estimate produces a strictly lower optimized target.
    """
    base_kwargs = dict(
        session_id="sess_t1",
        user_id="user_t1",
        focused_minutes_used=10.0,
        planned_minutes=45.0,
        purpose="entertainment",
        timer_mode="planned",
        temptation_confidence=0.9,
        contextual_baseline=45.0,
        necessary_minimum=10.0,
        cross_domain_allowance=120.0,
        tracking_reliability=1.0,
    )

    res_low = optimizer.solve(temptation_estimate=0.1, **base_kwargs)
    res_high = optimizer.solve(temptation_estimate=0.9, **base_kwargs)

    assert res_low["solver_status"] == "OPTIMIZED"
    assert res_high["solver_status"] == "OPTIMIZED"
    assert res_high["optimized_target"] < res_low["optimized_target"], (
        f"Expected target to strictly decrease with temptation, but got "
        f"low={res_low['optimized_target']} vs high={res_high['optimized_target']}"
    )


def test_higher_temptation_respects_protected_minimum_when_binding(optimizer):
    """
    Test 2: With the necessary-minimum/utility constraint binding,
    higher temptation does not push the target below the protected minimum.
    """
    nec_min = 25.0
    base_kwargs = dict(
        session_id="sess_t2",
        user_id="user_t2",
        focused_minutes_used=10.0,
        planned_minutes=15.0,
        purpose="work_study",
        timer_mode="planned",
        temptation_confidence=0.9,
        contextual_baseline=20.0,
        necessary_minimum=nec_min,
        cross_domain_allowance=120.0,
        tracking_reliability=1.0,
    )

    res_extreme_temptation = optimizer.solve(temptation_estimate=1.0, **base_kwargs)

    assert res_extreme_temptation["solver_status"] == "OPTIMIZED"
    assert res_extreme_temptation["optimized_target"] >= nec_min, (
        f"Optimized target {res_extreme_temptation['optimized_target']} fell below "
        f"protected minimum {nec_min}"
    )


def test_temptation_cost_increases_with_temptation_estimate_for_same_candidate(optimizer):
    """
    Test 3: For the same candidate x, the temptation-related objective cost
    increases when temptation_estimate increases.
    """
    x_candidate = 30.0
    beta = optimizer.beta
    session_scale = optimizer.session_scale

    tempt_low = 0.2
    tempt_high = 0.8

    cost_low = beta * tempt_low * (x_candidate / session_scale)
    cost_high = beta * tempt_high * (x_candidate / session_scale)

    assert cost_high > cost_low, (
        f"Expected temptation cost for candidate x={x_candidate} to increase from "
        f"low ({cost_low}) to high ({cost_high})"
    )


def test_research_derivation_records_temptation_fields(optimizer):
    """
    Test 4: The research derivation records:
      - temptation_estimate
      - beta
      - temptation cost
      - parameter source
      - selected objective value
    """
    res = optimizer.solve(
        session_id="sess_t4",
        user_id="user_t4",
        focused_minutes_used=5.0,
        planned_minutes=30.0,
        purpose="entertainment",
        timer_mode="planned",
        temptation_estimate=0.4,
        temptation_confidence=0.8,
        contextual_baseline=30.0,
        necessary_minimum=5.0,
        cross_domain_allowance=120.0,
    )

    assert res["solver_status"] == "OPTIMIZED"
    derivation = res["derivation"]

    assert "temptation_estimate" in derivation
    assert derivation["temptation_estimate"] == 0.4

    assert "beta" in derivation
    assert derivation["beta"] == optimizer.beta

    assert "temptation_cost" in derivation
    assert derivation["temptation_cost"] >= 0.0

    assert "selected_objective_value" in derivation
    assert derivation["selected_objective_value"] == res["objective_value"]

    assert "parameter_sources" in derivation
    assert derivation["parameter_sources"].get("beta") == SOURCE_VERSIONED_DEFAULT
