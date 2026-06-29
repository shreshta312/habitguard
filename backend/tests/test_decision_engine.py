from app.services.decision_engine import DecisionEngine


def test_calibration_returns_no_intervention():
    engine = DecisionEngine()

    timer_result = {
        "mode": "CALIBRATION",
        "timer_active": False,
        "message": "Collecting baseline data. 5 more days needed."
    }

    decision = engine.decide(timer_result)

    assert decision["mode"] == "CALIBRATION"
    assert decision["should_intervene"] is False
    assert decision["friction_type"] == "NONE"
    assert decision["recommended_timer_minutes"] is None


def test_stable_usage_no_context_returns_no_intervention():
    engine = DecisionEngine()

    timer_result = {
        "mode": "ACTIVE",
        "timer_active": True,
        "recommended_timer_minutes": 40,
        "overuse_gap_minutes": 0,
        "baseline_usage_minutes": 40,
        "recent_usage_minutes": 40,
        "rho_user": 0.3
    }

    decision = engine.decide(timer_result)

    assert decision["usage_status"] == "STABLE"
    assert decision["friction_type"] == "NONE"
    assert decision["should_intervene"] is False


def test_temptation_long_session_escalates_stable_usage():
    engine = DecisionEngine()

    timer_result = {
        "mode": "ACTIVE",
        "timer_active": True,
        "recommended_timer_minutes": 40,
        "overuse_gap_minutes": 0,
        "baseline_usage_minutes": 40,
        "recent_usage_minutes": 40,
        "rho_user": 0.3
    }

    context = {
        "current_domain": "youtube.com",
        "current_category": "temptation",
        "session_minutes": 15
    }

    decision = engine.decide(timer_result, context)

    assert decision["usage_status"] == "TEMPTATION_SESSION"
    assert decision["friction_type"] == "SOFT_WARNING"
    assert decision["should_intervene"] is True


def test_productive_context_reduces_timer_warning():
    engine = DecisionEngine()

    timer_result = {
        "mode": "ACTIVE",
        "timer_active": True,
        "recommended_timer_minutes": 35,
        "overuse_gap_minutes": 20,
        "baseline_usage_minutes": 40,
        "recent_usage_minutes": 60,
        "rho_user": 0.3
    }

    context = {
        "current_domain": "leetcode.com",
        "current_category": "productive",
        "session_minutes": 25
    }

    decision = engine.decide(timer_result, context)

    assert decision["usage_status"] == "PRODUCTIVE_CONTEXT"
    assert decision["friction_type"] == "SOFT_WARNING"
    assert decision["should_intervene"] is True


def test_temptation_high_overuse_escalates_to_strong_friction():
    engine = DecisionEngine()

    timer_result = {
        "mode": "ACTIVE",
        "timer_active": True,
        "recommended_timer_minutes": 25,
        "overuse_gap_minutes": 25,
        "baseline_usage_minutes": 40,
        "recent_usage_minutes": 65,
        "rho_user": 0.3
    }

    context = {
        "current_domain": "instagram.com",
        "current_category": "temptation",
        "session_minutes": 20
    }

    decision = engine.decide(timer_result, context)

    assert decision["usage_status"] == "RISKY_TEMPTATION_USAGE"
    assert decision["friction_type"] == "STRONG_FRICTION"
    assert decision["should_intervene"] is True