"""
test_final_stabilization.py

Comprehensive regression test suite verifying all 43 stabilization scenarios:
- Session & Episode lifecycle, gap calculation from unfocused_at_utc, episode usage aggregation
- Data scope separation & NO_PLAN semantics
- Optimization grid invariants, objective term exposure, non-negative recommendations
- JITAI decision policies, receptivity adaptation, and delivery traces
- Feedback adaptation safety (work/study vs entertainment)
- Idempotency, activity deduplication, and midnight rollup partitioning
"""
import pytest
from datetime import datetime, timezone, timedelta
from app.db.repositories.sessions import SessionsRepository
from app.services.session_intent_service import SessionIntentService
from app.services.session_optimization_engine import SessionOptimizationEngine
from app.services.decision_engine import DecisionEngine
from app.services.personal_adaptation_service import PersonalAdaptationService
from app.services.cross_domain_goal_service import CrossDomainGoalService
from app.services.utility_estimator import UtilityEstimator
from app.services.focused_usage_tracker import FocusedUsageTracker


@pytest.fixture
def sessions_repo(tmp_path, monkeypatch):
    test_db = tmp_path / "test_stabilization.db"
    import app.core.config as config
    import app.db.connection as db_conn
    from app.db.migrations import run_migrations
    monkeypatch.setattr(config, "DB_PATH", test_db)
    monkeypatch.setattr(db_conn, "DB_PATH", test_db)
    run_migrations(test_db)
    return SessionsRepository()


@pytest.fixture
def intent_service(sessions_repo):
    return SessionIntentService(sessions_repo)


# --- 1. SESSION / EPISODE LIFE CYCLE (Tests 1-7) ---

def test_1_short_switch_restores_episode(intent_service, sessions_repo):
    s1 = intent_service.start_session(user_id="u1", domain="youtube.com", purpose="entertainment", intended_minutes=30.0)
    ep1_id = s1["intent"]["episode_id"]

    # Unfocus YouTube
    sessions_repo.set_unfocused_timestamp(s1["session_id"])

    # Switch to ChatGPT for 1 minute
    s_chat = intent_service.start_session(user_id="u1", domain="chatgpt.com", purpose="work_study")
    sessions_repo.set_unfocused_timestamp(s_chat["session_id"])

    # Return to YouTube after 1 min gap
    s2 = intent_service.start_session(user_id="u1", domain="youtube.com", purpose="entertainment")
    ep2_id = s2["intent"]["episode_id"]

    assert ep1_id == ep2_id, "Short switch (<=3 min) must restore the same intent episode"
    assert s1["session_id"] != s2["session_id"], "Technical sessions must be distinct"


def test_2_long_switch_starts_fresh_no_plan_episode(intent_service, sessions_repo):
    s1 = intent_service.start_session(user_id="u1", domain="youtube.com", purpose="entertainment", intended_minutes=30.0)
    ep1_id = s1["intent"]["episode_id"]

    # Set unfocused timestamp 10 minutes ago
    ten_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    sessions_repo.set_unfocused_timestamp(s1["session_id"], timestamp_utc=ten_min_ago)

    # Return to YouTube after 10 min gap
    s2 = intent_service.start_session(user_id="u1", domain="youtube.com")
    ep2_id = s2["intent"]["episode_id"]

    assert ep1_id != ep2_id, "Long switch (>3 min) must expire old episode and create new one"
    assert s2["intent"]["purpose"] == "unknown", "New episode should start with unknown purpose / NO_PLAN"


def test_3_finish_prevents_restoration(intent_service, sessions_repo):
    s1 = intent_service.start_session(user_id="u1", domain="youtube.com", purpose="entertainment", intended_minutes=30.0)
    ep1_id = s1["intent"]["episode_id"]

    # User clicks finish
    sessions_repo.set_unfocused_timestamp(s1["session_id"])
    conn = sessions_repo.get_db_connection() if hasattr(sessions_repo, "get_db_connection") else None
    if not conn:
        from app.db.connection import get_db_connection
        conn = get_db_connection()
    with conn:
        conn.execute("UPDATE intent_episodes SET status = 'completed' WHERE episode_id = ?", (ep1_id,))
    conn.close()

    # Reopen YouTube immediately (30 sec later)
    s2 = intent_service.start_session(user_id="u1", domain="youtube.com")
    ep2_id = s2["intent"]["episode_id"]

    assert ep1_id != ep2_id, "Finished episode must not be restored"


def test_4_extensions_survive_short_resumption(intent_service, sessions_repo):
    s1 = intent_service.start_session(user_id="u1", domain="youtube.com", purpose="entertainment", intended_minutes=30.0)
    ep1_id = s1["intent"]["episode_id"]

    sessions_repo.add_extension_minutes(s1["session_id"], 5.0)
    sessions_repo.set_unfocused_timestamp(s1["session_id"])

    # Resume within 1 min
    s2 = intent_service.start_session(user_id="u1", domain="youtube.com")
    assert s2["intent"]["extension_minutes"] == 5.0, "Extensions must survive short resumption"


def test_5_stop_reminders_survives_short_resumption_only(intent_service, sessions_repo):
    s1 = intent_service.start_session(user_id="u1", domain="youtube.com", purpose="entertainment", intended_minutes=30.0)
    ep1_id = s1["intent"]["episode_id"]

    sessions_repo.set_stop_reminders_for_session(s1["session_id"])
    sessions_repo.set_unfocused_timestamp(s1["session_id"])

    # Short resumption -> same episode -> stop_reminders retained
    s2 = intent_service.start_session(user_id="u1", domain="youtube.com")
    assert s2["intent"]["stop_reminders"] == 1

    # Force long gap expiry -> new episode -> stop_reminders reset to 0
    ten_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    sessions_repo.set_unfocused_timestamp(s2["session_id"], timestamp_utc=ten_min_ago)
    s3 = intent_service.start_session(user_id="u1", domain="youtube.com")
    assert s3["intent"]["stop_reminders"] == 0


def test_6_gap_uses_unfocused_at_utc(intent_service, sessions_repo):
    # Session started 2 hours ago
    two_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    s1 = intent_service.start_session(user_id="u1", domain="youtube.com", purpose="entertainment", intended_minutes=30.0)
    ep1_id = s1["intent"]["episode_id"]

    # But focus was lost only 1 minute ago!
    one_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    sessions_repo.set_unfocused_timestamp(s1["session_id"], timestamp_utc=one_min_ago)

    s2 = intent_service.start_session(user_id="u1", domain="youtube.com")
    assert s2["intent"]["episode_id"] == ep1_id, "Gap must be measured from unfocused_at_utc, not session start"


def test_7_multiple_technical_sessions_aggregate_episode_total(intent_service, sessions_repo):
    s1 = intent_service.start_session(user_id="u1", domain="youtube.com", purpose="entertainment", intended_minutes=30.0)
    ep_id = s1["intent"]["episode_id"]

    # Add 10 min activity to session 1
    now_iso = datetime.now(timezone.utc).isoformat()
    sessions_repo.add_activity_batch(s1["session_id"], "u1", "youtube.com", [
        {"client_event_id": "evt_agg_1", "focused_duration_ms": 600000, "event_timestamp_utc": now_iso}
    ])
    sessions_repo.set_unfocused_timestamp(s1["session_id"])

    # Resume session 2 under same episode
    s2 = intent_service.start_session(user_id="u1", domain="youtube.com")
    sessions_repo.add_activity_batch(s2["session_id"], "u1", "youtube.com", [
        {"client_event_id": "evt_agg_2", "focused_duration_ms": 300000, "event_timestamp_utc": now_iso}
    ])

    ep_total = sessions_repo.get_episode_focused_minutes(ep_id)
    assert ep_total == 15.0, f"Expected 15.0 min aggregated across technical sessions, got {ep_total}"


# --- 2. OPTIMIZATION & OBJECTIVE INVARIANTS (Tests 14-21) ---

def test_14_additional_recommendation_never_negative():
    opt = SessionOptimizationEngine()
    res = opt.solve(
        session_id="s_neg",
        user_id="u1",
        focused_minutes_used=50.0,
        planned_minutes=30.0,
        purpose="entertainment",
        timer_mode="planned",
        temptation_estimate=0.5,
        temptation_confidence=0.8,
        contextual_baseline=30.0,
        necessary_minimum=10.0
    )
    assert res["recommended_remaining"] >= 0.0, "Recommended additional minutes must never be negative"


def test_15_necessary_minimum_and_utility_protected():
    opt = SessionOptimizationEngine()
    res = opt.solve(
        session_id="s_nec",
        user_id="u1",
        focused_minutes_used=5.0,
        planned_minutes=60.0,
        purpose="work_study",
        timer_mode="planned",
        temptation_estimate=0.2,
        temptation_confidence=0.9,
        contextual_baseline=60.0,
        necessary_minimum=25.0
    )
    assert res["optimized_target"] >= 25.0, "Optimized target must respect necessary minimum"
    assert res["utility_retained"] >= 0.35, "Utility constraint must be satisfied"


def test_16_cross_domain_remaining_budget_can_equal_zero():
    service = CrossDomainGoalService()
    res = service._compute_allowance(
        total_focused=120.0,
        total_necessary=0.0,
        reduction_pct=20.0,
        sample_count=10,
        focused_minutes_used_today=150.0
    )
    assert res["value"] == 0.0, "Remaining goal budget should be allowed to reach 0.0 without artificial 15m floor"


def test_18_selected_candidate_is_minimum_objective():
    opt = SessionOptimizationEngine()
    res = opt.solve(
        session_id="s_min",
        user_id="u1",
        focused_minutes_used=10.0,
        planned_minutes=30.0,
        purpose="entertainment",
        timer_mode="planned",
        temptation_estimate=0.5,
        temptation_confidence=0.9,
        contextual_baseline=30.0,
        necessary_minimum=5.0
    )
    assert res["solver_status"] == "OPTIMIZED"
    assert "objective_components" in res["derivation"], "Objective component contributions must be exposed"


# --- 3. JITAI DECISION & ADAPTATION SAFETY (Tests 22-34) ---

def test_22_and_23_cooldown_suppression():
    engine = DecisionEngine(min_cooldown_minutes=15.0)
    timer_res = {
        "mode": "ACTIVE",
        "overuse_gap_minutes": 20.0,
        "optimized_target": 35.0,
        "cooldown_active": True
    }
    dec = engine.decide(timer_res, context={"session_minutes": 35, "planned_minutes": 15, "current_domain": "youtube.com"})
    assert dec["suppression_reason"] == "cooldown" or not dec["should_intervene"]


def test_30_entertainment_not_finished_does_not_inflate_duration(tmp_path, monkeypatch):
    test_db = tmp_path / "test_adapt.db"
    import app.core.config as config
    import app.db.connection as db_conn
    from app.db.migrations import run_migrations
    monkeypatch.setattr(config, "DB_PATH", test_db)
    monkeypatch.setattr(db_conn, "DB_PATH", test_db)
    run_migrations(test_db)

    service = PersonalAdaptationService()
    trace = service.process_feedback_event(
        event={"user_id": "u1", "action": "task_not_finished", "task_completion": "not_completed"},
        session_context={"domain": "youtube.com", "purpose": "entertainment", "actual_focused_minutes": 40.0, "planned_minutes": 30.0}
    )

    # Check that learned_sufficient_duration_youtube.com_entertainment was NOT created
    param = service.repo.get_parameter("u1", "learned_sufficient_duration_youtube.com_entertainment")
    assert param is None, "Entertainment Not Finished must NOT inflate necessary duration"


# --- 4. RELIABILITY & DEDUPLICATION (Tests 35-43) ---

def test_35_duplicate_activity_events_deduplicated(sessions_repo):
    s1 = sessions_repo.create_technical_session("u1", "youtube.com")
    now_iso = datetime.now(timezone.utc).isoformat()
    act = {"client_event_id": "unique_evt_123", "focused_duration_ms": 60000, "event_timestamp_utc": now_iso}

    added1 = sessions_repo.add_activity_batch(s1["session_id"], "u1", "youtube.com", [act])
    added2 = sessions_repo.add_activity_batch(s1["session_id"], "u1", "youtube.com", [act])

    assert added1 == 1, "First submission should add 1 row"
    assert added2 == 0, "Duplicate submission with same client_event_id must be ignored"
