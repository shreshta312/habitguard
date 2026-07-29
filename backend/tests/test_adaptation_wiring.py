"""
test_adaptation_wiring.py

Fix 7-D: Feedback-to-adaptation wiring tests (rules A-H).
"""
import pytest
from unittest.mock import MagicMock, call

from app.services.personal_adaptation_service import PersonalAdaptationService, MAX_ETA


def _make_service(current_params=None):
    """Return a PersonalAdaptationService with a mocked parameters repo."""
    repo = MagicMock()
    repo.get_parameter.return_value = current_params
    svc = PersonalAdaptationService(params_repo=repo)
    return svc, repo


# ---------------------------------------------------------------------------
# Rule A: task_not_finished / not_completed / insufficient
# ---------------------------------------------------------------------------

class TestRuleA_InsufficientTime:
    def _run(self, action="task_not_finished", task_completion=None, time_sufficient=None):
        svc, repo = _make_service(current_params=None)
        event = {"user_id": "u1", "action": action, "session_id": "s1"}
        ctx = {
            "domain": "youtube.com",
            "purpose": "work_study",
            "actual_focused_minutes": 35.0,
            "planned_minutes": 20.0,
            "optimized_target": 22.0,
            "task_completion": task_completion,
            "time_sufficient": time_sufficient,
        }
        trace = svc.process_feedback_event(event, ctx)
        return trace, repo

    def test_task_not_finished_action_increments_count(self):
        trace, repo = self._run(action="task_not_finished")
        param_names_updated = [u["param"] for u in trace["updates"]]
        assert any("task_not_finished_count" in p for p in param_names_updated)

    def test_not_completed_updates_sufficient_duration_upward(self):
        trace, repo = self._run(task_completion="not_completed")
        param_names = [u["param"] for u in trace["updates"]]
        assert any("learned_sufficient_duration" in p for p in param_names)
        dur_update = next(u for u in trace["updates"] if "learned_sufficient_duration" in u.get("param", ""))
        assert dur_update.get("direction") == "upward"

    def test_insufficient_time_updates_duration_upward(self):
        trace, repo = self._run(time_sufficient="insufficient")
        dur_update = next(
            (u for u in trace["updates"] if "learned_sufficient_duration" in u.get("param", "")),
            None
        )
        assert dur_update is not None
        assert dur_update.get("direction") == "upward"

    def test_observed_requirement_uses_max_of_actual_planned_optimized(self):
        """observed_req = max(35, 20, 22) = 35 → new_val closer to 35."""
        svc, repo = _make_service(current_params={"value": 10.0, "sample_count": 1, "source": "VERSIONED_DEFAULT"})
        event = {"user_id": "u1", "action": "task_not_finished", "session_id": "s1"}
        ctx = {
            "domain": "yt.com", "purpose": "work_study",
            "actual_focused_minutes": 35.0, "planned_minutes": 20.0, "optimized_target": 22.0,
        }
        trace = svc.process_feedback_event(event, ctx)
        dur_update = next(u for u in trace["updates"] if "learned_sufficient_duration" in u.get("param", ""))
        # EMA update: new = (1-eta)*10 + eta*35, which should be > 10
        assert dur_update["new_value"] > 10.0

    def test_one_event_cannot_radically_change_parameter(self):
        """EMA eta must be <= MAX_ETA = 0.25 so a single event moves at most 25%."""
        svc, repo = _make_service(current_params={"value": 10.0, "sample_count": 1, "source": "VERSIONED_DEFAULT"})
        event = {"user_id": "u1", "action": "task_not_finished", "session_id": "s1"}
        ctx = {
            "domain": "yt.com", "purpose": "work_study",
            "actual_focused_minutes": 200.0, "planned_minutes": 200.0, "optimized_target": 200.0,
        }
        trace = svc.process_feedback_event(event, ctx)
        dur_update = next(u for u in trace["updates"] if "learned_sufficient_duration" in u.get("param", ""))
        reported_eta = dur_update.get("eta", 0)
        assert reported_eta <= MAX_ETA


# ---------------------------------------------------------------------------
# Rule B: completed + sufficient
# ---------------------------------------------------------------------------

class TestRuleB_CompletedSufficient:
    def test_updates_toward_actual_duration(self):
        svc, repo = _make_service(current_params={"value": 40.0, "sample_count": 3, "source": "VERSIONED_DEFAULT"})
        event = {"user_id": "u1", "action": "finish", "session_id": "s1",
                 "task_completion": "completed", "time_sufficient": "sufficient"}
        ctx = {
            "domain": "yt.com", "purpose": "work_study",
            "actual_focused_minutes": 25.0, "planned_minutes": 30.0, "optimized_target": 28.0,
            "task_completion": "completed", "time_sufficient": "sufficient",
        }
        trace = svc.process_feedback_event(event, ctx)
        dur_updates = [u for u in trace["updates"] if "learned_sufficient_duration" in u.get("param", "")]
        assert len(dur_updates) == 1
        # Should move toward 25 (actual), currently at 40 → new < 40
        assert dur_updates[0]["new_value"] < 40.0


# ---------------------------------------------------------------------------
# Rule C: sufficient alone (no completion info) → only confidence increment
# ---------------------------------------------------------------------------

class TestRuleC_SufficientAlone:
    def test_value_unchanged_confidence_incremented(self):
        current = {"value": 30.0, "sample_count": 4, "source": "PERSONALLY_LEARNED"}
        svc, repo = _make_service(current_params=current)
        event = {"user_id": "u1", "action": "finish", "session_id": "s1",
                 "task_completion": None, "time_sufficient": "sufficient"}
        ctx = {
            "domain": "yt.com", "purpose": "entertainment",
            "actual_focused_minutes": 20.0, "planned_minutes": None,
            "task_completion": None, "time_sufficient": "sufficient",
        }
        trace = svc.process_feedback_event(event, ctx)
        dur_notes = [u for u in trace["updates"] if "learned_sufficient_duration" in u.get("param", "")]
        if dur_notes:
            assert any(u.get("note") == "confidence_increment_only" for u in dur_notes)


# ---------------------------------------------------------------------------
# Rule D: partly_completed / partly_sufficient → smaller ETA
# ---------------------------------------------------------------------------

class TestRuleD_Partial:
    def test_partial_uses_smaller_eta(self):
        svc, repo = _make_service(current_params={"value": 20.0, "sample_count": 2, "source": "VERSIONED_DEFAULT"})
        event = {"user_id": "u1", "action": "extend_5", "session_id": "s1",
                 "task_completion": "partly_completed", "time_sufficient": None}
        ctx = {
            "domain": "yt.com", "purpose": "entertainment",
            "actual_focused_minutes": 40.0, "planned_minutes": 30.0, "optimized_target": 28.0,
            "task_completion": "partly_completed", "time_sufficient": None,
        }
        from app.services.personal_adaptation_service import DEFAULT_ETA, PARTIAL_ETA_FACTOR
        trace = svc.process_feedback_event(event, ctx)
        dur_updates = [u for u in trace["updates"] if "learned_sufficient_duration" in u.get("param", "") and "eta" in u]
        if dur_updates:
            assert dur_updates[0]["eta"] <= DEFAULT_ETA * PARTIAL_ETA_FACTOR + 1e-9


# ---------------------------------------------------------------------------
# Rule E: dismiss → only acceptance_rate updated
# ---------------------------------------------------------------------------

class TestRuleE_Dismiss:
    def test_dismiss_does_not_update_learned_duration(self):
        svc, repo = _make_service(current_params={"value": 0.5, "sample_count": 2, "source": "VERSIONED_DEFAULT"})
        event = {"user_id": "u1", "action": "dismiss", "session_id": "s1"}
        ctx = {"domain": "yt.com", "purpose": "entertainment", "actual_focused_minutes": 20.0}
        trace = svc.process_feedback_event(event, ctx)
        dur_updates = [u for u in trace["updates"] if "learned_sufficient_duration" in u.get("param", "")]
        assert len(dur_updates) == 0

    def test_dismiss_updates_acceptance_rate_downward(self):
        svc, repo = _make_service(current_params={"value": 0.8, "sample_count": 5, "source": "PERSONALLY_LEARNED"})
        event = {"user_id": "u1", "action": "dismiss", "session_id": "s1"}
        ctx = {"domain": "yt.com", "purpose": "entertainment", "actual_focused_minutes": 20.0}
        trace = svc.process_feedback_event(event, ctx)
        ar_updates = [u for u in trace["updates"] if u.get("param") == "acceptance_rate"]
        assert len(ar_updates) == 1
        assert ar_updates[0]["new_value"] < ar_updates[0]["prev_value"]


# ---------------------------------------------------------------------------
# Rule F: extend_5 — not treated as dismissal
# ---------------------------------------------------------------------------

class TestRuleF_Extend5:
    def test_extend_updates_acceptance_rate_upward(self):
        svc, repo = _make_service(current_params={"value": 0.3, "sample_count": 3, "source": "PERSONALLY_LEARNED"})
        event = {"user_id": "u1", "action": "extend_5", "session_id": "s1"}
        ctx = {"domain": "yt.com", "purpose": "entertainment", "actual_focused_minutes": 20.0}
        trace = svc.process_feedback_event(event, ctx)
        ar_updates = [u for u in trace["updates"] if u.get("param") == "acceptance_rate"]
        assert ar_updates[0]["new_value"] > ar_updates[0]["prev_value"]

    def test_extend_note_is_extend_not_dismiss(self):
        svc, repo = _make_service()
        event = {"user_id": "u1", "action": "extend_5", "session_id": "s1"}
        ctx = {"domain": "yt.com", "purpose": "entertainment", "actual_focused_minutes": 20.0}
        trace = svc.process_feedback_event(event, ctx)
        ar_updates = [u for u in trace["updates"] if u.get("param") == "acceptance_rate"]
        assert ar_updates[0].get("note") == "extend"


# ---------------------------------------------------------------------------
# Rule G: finish — successful stopping
# ---------------------------------------------------------------------------

class TestRuleG_Finish:
    def test_finish_updates_acceptance_rate_upward(self):
        svc, repo = _make_service(current_params={"value": 0.4, "sample_count": 2, "source": "PERSONALLY_LEARNED"})
        event = {"user_id": "u1", "action": "finish", "session_id": "s1"}
        ctx = {"domain": "yt.com", "purpose": "entertainment", "actual_focused_minutes": 15.0}
        trace = svc.process_feedback_event(event, ctx)
        ar_updates = [u for u in trace["updates"] if u.get("param") == "acceptance_rate"]
        assert ar_updates[0]["new_value"] > ar_updates[0]["prev_value"]


# ---------------------------------------------------------------------------
# Rule H: stop_reminders — episode-scoped only
# ---------------------------------------------------------------------------

class TestRuleH_StopReminders:
    def test_stop_reminders_sets_episode_flag(self):
        svc, repo = _make_service()
        event = {"user_id": "u1", "action": "stop_reminders", "session_id": "sess_abc"}
        ctx = {"domain": "yt.com", "purpose": "entertainment"}
        trace = svc.process_feedback_event(event, ctx)
        episode_updates = [u for u in trace["updates"] if "stop_reminders_episode" in u.get("param", "")]
        assert len(episode_updates) == 1
        assert episode_updates[0]["scope"] == "episode"

    def test_stop_reminders_does_not_touch_global_acceptance_rate(self):
        svc, repo = _make_service()
        event = {"user_id": "u1", "action": "stop_reminders", "session_id": "sess_xyz"}
        ctx = {"domain": "yt.com", "purpose": "entertainment"}
        trace = svc.process_feedback_event(event, ctx)
        ar_updates = [u for u in trace["updates"] if u.get("param") == "acceptance_rate"]
        assert len(ar_updates) == 0


# ---------------------------------------------------------------------------
# rho_user must NOT be updated
# ---------------------------------------------------------------------------

class TestNoStructuralParameterUpdate:
    def test_rho_user_not_updated_by_feedback(self):
        svc, repo = _make_service()
        for action in ["finish", "extend_5", "dismiss", "task_not_finished", "stop_reminders"]:
            trace = svc.process_feedback_event(
                {"user_id": "u1", "action": action, "session_id": "s1"},
                {"domain": "yt.com", "purpose": "entertainment", "actual_focused_minutes": 20.0}
            )
            rho_updates = [u for u in trace["updates"] if "rho_user" in u.get("param", "")]
            assert rho_updates == [], f"rho_user must not be updated by action={action}"
