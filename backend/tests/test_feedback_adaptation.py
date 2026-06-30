from app.services.decision_engine import DecisionEngine


def _active_timer_result(overuse_gap):
    return {
        "mode": "ACTIVE",
        "timer_active": True,
        "recommended_timer_minutes": 20,
        "overuse_gap_minutes": overuse_gap,
        "baseline_usage_minutes": 30,
        "recent_usage_minutes": 30 + overuse_gap,
        "rho_user": 0.4
    }


def test_feedback_suppresses_repeatedly_dismissed_site():
    engine = DecisionEngine(min_feedback_events=3)

    feedback_summary = {
        "total_events": 3,
        "event_type_counts": {
            "overlay_dismissed": 3,
            "break_accepted": 0
        },
        "overlay_dismissed_count": 3,
        "break_accepted_count": 0,
        "break_acceptance_rate": 0.0,
        "most_dismissed_sites": [
            ["youtube.com", 3]
        ],
        "most_accepted_break_sites": []
    }

    result = engine.decide(
        timer_result=_active_timer_result(overuse_gap=5),
        context={
            "current_domain": "youtube.com",
            "current_category": "neutral",
            "session_minutes": 5
        },
        feedback_summary=feedback_summary
    )

    assert result["should_intervene"] is False
    assert result["friction_type"] == "NONE"
    assert result["feedback_adaptation_used"] is True


def test_feedback_softens_global_low_acceptance():
    engine = DecisionEngine(min_feedback_events=3)

    feedback_summary = {
        "total_events": 5,
        "event_type_counts": {
            "overlay_dismissed": 5,
            "break_accepted": 0
        },
        "overlay_dismissed_count": 5,
        "break_accepted_count": 0,
        "break_acceptance_rate": 0.0,
        "most_dismissed_sites": [],
        "most_accepted_break_sites": []
    }

    result = engine.decide(
        timer_result=_active_timer_result(overuse_gap=35),
        context={
            "current_domain": "reddit.com",
            "current_category": "neutral",
            "session_minutes": 40
        },
        feedback_summary=feedback_summary
    )

    assert result["should_intervene"] is True
    assert result["friction_type"] == "TIMER_WARNING"
    assert result["feedback_adaptation_used"] is True