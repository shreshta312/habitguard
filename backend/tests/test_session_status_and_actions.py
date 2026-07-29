"""
test_session_status_and_actions.py

Tests proving session_status, OVER_PLAN message override, suppression_reason,
and canonical action processing.
"""
import pytest
from app.services.decision_engine import DecisionEngine
from app.services.session_intent_service import SessionIntentService
from app.services.focused_usage_tracker import FocusedUsageTracker
from app.services.session_optimization_engine import SessionOptimizationEngine
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

@pytest.fixture
def decision_engine():
    return DecisionEngine()

def test_session_status_over_plan(decision_engine):
    """Proves Used 6 / Planned 3 produces session_status OVER_PLAN."""
    timer_result = {
        "mode": "ACTIVE",
        "overuse_gap_minutes": 0,
        "recommended_timer_minutes": 15,
        "planned_minutes": 3.0
    }
    context = {
        "session_minutes": 6.0,
        "planned_minutes": 3.0,
        "current_domain": "youtube.com"
    }
    res = decision_engine.decide(timer_result, context=context)
    assert res["session_status"] == "OVER_PLAN"
    assert "within normal limits" not in res["message"].lower()
    assert "Over plan" in res["message"]
    assert "3 min over" in res["message"]

def test_session_status_within_plan(decision_engine):
    """Proves Used 2 / Planned 3 produces session_status WITHIN_PLAN."""
    timer_result = {
        "mode": "ACTIVE",
        "overuse_gap_minutes": 0,
        "planned_minutes": 3.0
    }
    context = {
        "session_minutes": 2.0,
        "planned_minutes": 3.0,
        "current_domain": "youtube.com"
    }
    res = decision_engine.decide(timer_result, context=context)
    assert res["session_status"] == "WITHIN_PLAN"

def test_session_status_no_plan(decision_engine):
    """Proves missing plan produces session_status NO_PLAN."""
    timer_result = {
        "mode": "ACTIVE",
        "overuse_gap_minutes": 0,
        "planned_minutes": None
    }
    context = {
        "session_minutes": 5.0,
        "planned_minutes": None,
        "current_domain": "youtube.com"
    }
    res = decision_engine.decide(timer_result, context=context)
    assert res["session_status"] == "NO_PLAN"

def test_over_plan_never_renders_within_normal_limits(decision_engine):
    """Proves OVER_PLAN never renders 'within normal limits'."""
    timer_result = {
        "mode": "ACTIVE",
        "overuse_gap_minutes": 0.0,
        "planned_minutes": 3.0
    }
    context = {
        "session_minutes": 6.0,
        "planned_minutes": 3.0,
        "current_domain": "youtube.com"
    }
    res = decision_engine.decide(timer_result, context=context)
    assert res["session_status"] == "OVER_PLAN"
    assert "within normal limits" not in res["message"].lower()

def test_should_intervene_false_independently_when_over_plan(decision_engine):
    """Proves should_intervene can remain false independently when OVER_PLAN."""
    timer_result = {
        "mode": "ACTIVE",
        "overuse_gap_minutes": 0.0,
        "planned_minutes": 3.0
    }
    context = {
        "session_minutes": 6.0,
        "planned_minutes": 3.0,
        "current_domain": "youtube.com"
    }
    res = decision_engine.decide(timer_result, context=context)
    assert res["session_status"] == "OVER_PLAN"
    assert res["should_intervene"] is False
    assert res["suppression_reason"] is not None
    assert res["suppression_reason"] in ["baseline_allowance", "small_absolute_overrun", "low_confidence", "cooldown", "prompt_burden"]

def test_suppression_reason_exists_when_over_plan_suppressed(decision_engine):
    """Proves suppression_reason exists when an over-plan intervention is suppressed."""
    timer_result = {
        "mode": "ACTIVE",
        "overuse_gap_minutes": 0.0,
        "solver_status": "LEARNING",
        "confidence": 0.1,
        "planned_minutes": 5.0
    }
    context = {
        "session_minutes": 10.0,
        "planned_minutes": 5.0,
        "current_domain": "youtube.com"
    }
    res = decision_engine.decide(timer_result, context=context)
    assert res["session_status"] == "OVER_PLAN"
    assert res["should_intervene"] is False
    assert res["suppression_reason"] == "low_confidence"

def test_canonical_action_endpoint_events():
    """Proves canonical action endpoint handles extend_5, task_not_finished, finish, stop_reminders."""
    start_res = client.post("/sessions/start", json={
        "user_id": "test_actions_user",
        "domain": "github.com",
        "purpose": "work_study",
        "intended_minutes": 25.0
    })
    assert start_res.status_code == 200
    session_id = start_res.json()["session_id"]

    res_ext = client.post(f"/sessions/{session_id}/action", json={"action": "extend_5"})
    assert res_ext.status_code == 200
    assert res_ext.json()["status"] == "success"

    res_nf = client.post(f"/sessions/{session_id}/action", json={
        "action": "task_not_finished",
        "task_completion": "not_completed",
        "time_sufficient": "insufficient"
    })
    assert res_nf.status_code == 200
    assert res_nf.json()["status"] == "success"

    res_fin = client.post(f"/sessions/{session_id}/action", json={
        "action": "finish",
        "task_completion": "unknown",
        "time_sufficient": "unknown"
    })
    assert res_fin.status_code == 200
    assert res_fin.json()["status"] == "success"

    res_sr = client.post(f"/sessions/{session_id}/action", json={"action": "stop_reminders"})
    assert res_sr.status_code == 200
    assert res_sr.json()["status"] == "success"
