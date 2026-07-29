from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

def local_date_for_timezone(timezone_name: str) -> str:
    try:
        tz = ZoneInfo(timezone_name or "UTC")
    except Exception:
        tz = timezone.utc

    return datetime.now(timezone.utc).astimezone(tz).date().isoformat()

from app.db.migrations import run_migrations
from app.core.config import SYSTEM_PARAMETERS, CONFIG_VERSION
from app.db.repositories.goals import GoalsRepository
from app.db.repositories.sessions import SessionsRepository
from app.db.repositories.feedback import FeedbackRepository
from app.db.repositories.optimization import OptimizationRepository
from app.db.repositories.parameters import PersonalParametersRepository
from app.db.repositories.rollups import DailyUsageRollupsRepository
from app.db.connection import get_db_connection

from app.services.focused_usage_tracker import FocusedUsageTracker
from app.services.session_intent_service import SessionIntentService
from app.services.behavior_feature_service import BehaviorFeatureService
from app.services.contextual_baseline_service import ContextualBaselineService
from app.services.temptation_estimator import TemptationEstimator
from app.services.utility_estimator import UtilityEstimator
from app.services.cross_domain_goal_service import CrossDomainGoalService
from app.services.session_optimization_engine import SessionOptimizationEngine
from app.services.decision_engine import DecisionEngine
from app.services.feedback_service import FeedbackService
from app.services.personal_adaptation_service import PersonalAdaptationService
from app.services.outcome_evaluation_service import OutcomeEvaluationService
from app.services.structural_timer_engine import StructuralTimerEngine
from app.services.habitguard_service import HabitGuardService

from app.api.feedback import router as feedback_router
from app.api.usage import router as usage_router

# Run database migrations on startup
run_migrations()

app = FastAPI(
    title="HabitGuard API",
    description="Temptation-aware browser usage optimization backend",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(feedback_router)
app.include_router(usage_router)

# Instantiate Repositories
from app.db.repositories.delivery_traces import DeliveryTracesRepository

goals_repo = GoalsRepository()
sessions_repo = SessionsRepository()
feedback_repo = FeedbackRepository()
opt_repo = OptimizationRepository()
params_repo = PersonalParametersRepository()
rollups_repo = DailyUsageRollupsRepository()
delivery_repo = DeliveryTracesRepository()

# Instantiate Canonical Pipeline Services
usage_tracker = FocusedUsageTracker(sessions_repo)
intent_service = SessionIntentService(sessions_repo)
feature_service = BehaviorFeatureService()
baseline_service = ContextualBaselineService(rollups_repo)
temptation_estimator = TemptationEstimator()
utility_estimator = UtilityEstimator()
cross_domain_service = CrossDomainGoalService(rollups_repo)
optimizer = SessionOptimizationEngine(utility_estimator)
decision_engine = DecisionEngine()
adaptation_service = PersonalAdaptationService(params_repo)
feedback_service = FeedbackService(feedback_repo, adaptation_service)
outcome_evaluator = OutcomeEvaluationService()
structural_timer_engine = StructuralTimerEngine()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = PROJECT_ROOT / "data" / "processed" / "cleaned_screen_time.csv"
habitguard_service = HabitGuardService(CSV_PATH)

# Models
class OnboardingRequest(BaseModel):
    user_id: str
    selected_domains: List[str]
    reduction_intensity: Optional[str] = "moderate"
    target_reduction_percent: Optional[float] = 20.0

class GoalUpdateRequest(BaseModel):
    selected_domains: Optional[List[str]] = None
    reduction_intensity: Optional[str] = None
    target_reduction_percent: Optional[float] = None

class SessionStartRequest(BaseModel):
    user_id: str
    domain: str
    purpose: Optional[str] = "unknown"
    intended_minutes: Optional[float] = None
    timer_mode: Optional[str] = "planned"
    remember_today: Optional[bool] = False
    local_timezone: Optional[str] = "UTC"

class IntentUpdateRequest(BaseModel):
    purpose: Optional[str] = None
    intended_minutes: Optional[float] = None
    timer_mode: Optional[str] = None

class ActionRequest(BaseModel):
    action: str # extend_5, finish, dismiss, not_finished, stop_reminders
    task_completion: Optional[str] = None # completed, not_completed, partly_completed
    time_sufficient: Optional[str] = None # sufficient, insufficient, partly_sufficient

class DeliveryTraceRequest(BaseModel):
    decision_id: str
    session_id: str
    episode_id: Optional[str] = None
    user_id: str = "local_user"
    domain: str
    channel: str = "none" # notification, overlay, none
    requested_channel: Optional[str] = "notification"
    fallback_channel: Optional[str] = None
    intervention_preserved: Optional[bool] = False
    should_notify: bool = False
    should_overlay: bool = False
    eligible: bool = False
    attempted_at_utc: Optional[str] = None
    delivery_status: str # NOT_ELIGIBLE, SUPPRESSED, PERMISSION_DENIED, ATTEMPTED, API_ACCEPTED, FAILED
    chrome_notification_id: Optional[str] = None
    failure_reason: Optional[str] = None
    cooldown_source: Optional[str] = "VERSIONED_DEFAULT"
    next_eligible_at: Optional[str] = None

class BatchActivityRequest(BaseModel):
    activities: List[Dict[str, Any]]
    current_category: Optional[str] = None

class LegacyContextRequest(BaseModel):
    current_domain: Optional[str] = None
    current_category: Optional[str] = None
    session_minutes: Optional[float] = None
    top_domains: Optional[Dict[str, float]] = None
    timestamp: Optional[int] = None

class LegacyCustomUsageRequest(BaseModel):
    user_id: str = "local_user"
    usage_history_minutes: List[float]
    context: Optional[LegacyContextRequest] = None


# ==========================================
# 1. USER ENDPOINTS
# ==========================================

@app.post("/onboarding")
def onboarding(req: OnboardingRequest):
    goal = goals_repo.upsert_goal(
        user_id=req.user_id,
        selected_domains=req.selected_domains,
        reduction_intensity=req.reduction_intensity or "moderate",
        target_reduction_percent=req.target_reduction_percent or 20.0
    )
    return {"status": "success", "goal": goal}

@app.get("/goals/{user_id}")
def get_goal(user_id: str):
    goal = goals_repo.get_goal(user_id)
    if not goal:
        goal = goals_repo.upsert_goal(user_id=user_id, selected_domains=["youtube.com", "instagram.com", "reddit.com"])
    return goal

@app.patch("/goals/{user_id}")
def update_goal(user_id: str, req: GoalUpdateRequest):
    existing = goals_repo.get_goal(user_id) or {}
    domains = req.selected_domains if req.selected_domains is not None else existing.get("selected_domains", [])
    intensity = req.reduction_intensity or existing.get("reduction_intensity", "moderate")
    percent = req.target_reduction_percent if req.target_reduction_percent is not None else existing.get("target_reduction_percent", 20.0)
    return goals_repo.upsert_goal(user_id, domains, intensity, percent)

@app.post("/sessions/start")
def start_session(req: SessionStartRequest):
    session = intent_service.start_session(
        user_id=req.user_id,
        domain=req.domain,
        purpose=req.purpose,
        intended_minutes=req.intended_minutes,
        timer_mode=req.timer_mode or "planned",
        remember_today=req.remember_today or False,
        local_timezone=req.local_timezone or "UTC"
    )
    return session

@app.get("/sessions/{session_id}")
def get_session(session_id: str):
    session = intent_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@app.post("/sessions/{session_id}/unfocus")
def record_session_unfocused(session_id: str, timestamp_utc: Optional[str] = None):
    sessions_repo.set_unfocused_timestamp(session_id, timestamp_utc)
    return {"status": "success", "session_id": session_id}

@app.post("/sessions/{session_id}/intent")
@app.patch("/sessions/{session_id}/intent")
def update_session_intent(session_id: str, req: IntentUpdateRequest):
    updated = intent_service.update_intent(
        session_id=session_id,
        purpose=req.purpose,
        intended_minutes=req.intended_minutes,
        timer_mode=req.timer_mode
    )
    return updated

@app.post("/sessions/{session_id}/activity/batch")
def add_activity_batch(session_id: str, req: BatchActivityRequest):
    session = intent_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    user_id = session["user_id"]
    domain  = session["domain"]

    track_res    = usage_tracker.process_activities(session_id, user_id, domain, req.activities)
    if track_res["events_rejected"] > 0 and len(req.activities) > 0 and track_res["events_added"] == 0:
        raise HTTPException(
            status_code=400,
            detail="Invalid activity timestamp or duration: event predates session start, is in future beyond tolerance, or has invalid duration."
        )

    intent                 = session.get("intent") or {}
    purpose                = intent.get("purpose", "unknown")
    if purpose == "no_timer":
        purpose = "unknown"
    local_tz               = session.get("local_timezone", "UTC")
    episode_id             = session.get("episode_id")

    original_intended_mins = intent.get("intended_minutes")
    extension_mins         = float(intent.get("extension_minutes", 0.0) or 0.0)
    timer_mode             = intent.get("timer_mode", "planned")
    stop_reminders_flag    = intent.get("stop_reminders", 0)

    if timer_mode == "no_timer" or original_intended_mins is None:
        effective_planned_mins = None
    else:
        effective_planned_mins = float(original_intended_mins) + extension_mins

    focused_mins = track_res["total_focused_minutes"]
    episode_focused_mins = sessions_repo.get_episode_focused_minutes(episode_id) if episode_id else focused_mins

    # Phase 6: Record interval ONLY for newly inserted activities with accurate allocation
    inserted_acts = track_res.get("inserted_activities", [])
    new_batch_minutes = sum(
        float(act.get("focused_duration_ms", 0) or 0) / 60000.0
        for act in inserted_acts
    )
    running_used_before = max(0.0, episode_focused_mins - new_batch_minutes)

    ordered_acts = sorted(
        inserted_acts,
        key=lambda act: act.get("event_timestamp_utc") or ""
    )

    for act in ordered_acts:
        duration_ms = float(act.get("focused_duration_ms", 0) or 0)
        if duration_ms <= 0:
            continue

        duration_minutes = duration_ms / 60000.0
        timestamp_utc = (
            act.get("event_timestamp_utc")
            or datetime.now(timezone.utc).isoformat()
        )

        rollups_repo.record_activity_interval(
            user_id=user_id,
            domain=domain,
            end_timestamp_utc=timestamp_utc,
            duration_ms=duration_ms,
            classification=purpose,
            local_timezone=local_tz,
            effective_planned_minutes=effective_planned_mins,
            used_before_minutes=running_used_before,
        )

        running_used_before += duration_minutes

    # Phase 2: Category validation
    valid_categories = {"productive", "mixed", "temptation", "neutral"}
    raw_cat = req.current_category or session.get("category")
    current_category = raw_cat if raw_cat in valid_categories else "neutral"

    # Phase 7: Calculate actual distracting usage today across monitored domains
    today_str = local_date_for_timezone(local_tz)
    today_rollups = rollups_repo.get_user_rollups(user_id, days=1)
    today_distracting = sum(
        max(0.0, float(r.get("focused_minutes", 0)) - float(r.get("necessary_minutes", 0)))
        for r in today_rollups
        if r.get("local_date") == today_str
    )
    focused_minutes_used_today = max(today_distracting, episode_focused_mins)

    cross_domain_ctx = cross_domain_service.get_cross_domain_context(
        user_id=user_id,
        current_domain=domain,
        days=7,
        focused_minutes_used_today=focused_minutes_used_today,
    )
    cross_domain_allowance = cross_domain_ctx["cross_domain_allowance_minutes"]

    # Phase 3: Derived real behavioral features
    reopen_cnt = sessions_repo.get_reopen_count(episode_id)
    hist_overrun_rate = sessions_repo.get_historical_overrun_rate(user_id)
    cross_switches = sessions_repo.get_ordered_cross_domain_switches(user_id, days=1)

    feedback_sum = feedback_service.get_summary(user_id)
    features = feature_service.extract_features(
        focused_minutes=episode_focused_mins,
        planned_minutes=effective_planned_mins,
        purpose=purpose,
        reopen_count=reopen_cnt,
        uninterrupted_minutes=focused_mins,
        cross_domain_switches=cross_switches,
        historical_overrun_rate=hist_overrun_rate,
        feedback_summary=feedback_sum
    )

    tempt_res = temptation_estimator.estimate(features, purpose=purpose)

    # Phase 4: Load contextual personal parameters
    dur_param = params_repo.get_parameter(user_id, f"learned_sufficient_duration_{domain}_{purpose}")
    learned_dur = float(dur_param["value"]) if dur_param else None
    count_param = params_repo.get_parameter(user_id, f"task_not_finished_count_{domain}")
    not_finished_cnt = int(count_param["value"]) if count_param else 0

    base_res            = baseline_service.get_baseline(user_id, domain, purpose)
    contextual_baseline = base_res["baseline_minutes"]

    util_res  = utility_estimator.estimate(
        purpose=purpose,
        planned_minutes=effective_planned_mins,
        contextual_baseline=contextual_baseline,
        learned_sufficient_duration=learned_dur,
        task_not_finished_count=not_finished_cnt
    )

    opt_res = optimizer.solve(
        session_id=session_id,
        user_id=user_id,
        focused_minutes_used=episode_focused_mins,
        planned_minutes=effective_planned_mins,
        purpose=purpose,
        timer_mode=timer_mode,
        temptation_estimate=tempt_res["temptation_estimate"],
        temptation_confidence=tempt_res["confidence"],
        contextual_baseline=contextual_baseline,
        necessary_minimum=util_res["necessary_minimum"],
        cross_domain_allowance=cross_domain_allowance,
        tracking_reliability=track_res["tracking_reliability"]
    )

    opt_res.setdefault("derivation", {})
    opt_res["derivation"]["cross_domain_context"] = cross_domain_ctx
    opt_res["derivation"]["original_intended_minutes"] = original_intended_mins
    opt_res["derivation"]["extension_minutes"] = extension_mins
    opt_res["derivation"]["effective_planned_minutes"] = effective_planned_mins
    opt_res["parameter_sources"]["cross_domain_allowance"] = cross_domain_ctx["allowance_source"]

    opt_repo.record_run(opt_res)

    if effective_planned_mins is None or effective_planned_mins <= 0:
        session_status = "NO_PLAN"
        overuse_gap = None
        remaining_mins = None
        unplanned_mins = 0.0
        unknown_mins = episode_focused_mins
        planned_mins_acc = None
    elif episode_focused_mins > effective_planned_mins:
        session_status = "OVER_PLAN"
        overuse_gap = round(episode_focused_mins - effective_planned_mins, 2)
        remaining_mins = 0.0
        unplanned_mins = overuse_gap
        unknown_mins = 0.0
        planned_mins_acc = effective_planned_mins
    elif episode_focused_mins >= max(0.0, effective_planned_mins - 2.0) and episode_focused_mins <= effective_planned_mins:
        session_status = "NEAR_PLAN"
        overuse_gap = 0.0
        remaining_mins = round(effective_planned_mins - episode_focused_mins, 2)
        unplanned_mins = 0.0
        unknown_mins = 0.0
        planned_mins_acc = episode_focused_mins
    else:
        session_status = "WITHIN_PLAN"
        overuse_gap = 0.0
        remaining_mins = round(effective_planned_mins - episode_focused_mins, 2)
        unplanned_mins = 0.0
        unknown_mins = 0.0
        planned_mins_acc = episode_focused_mins

    opt_res["overuse_gap_minutes"] = overuse_gap

    dec_res = decision_engine.decide(
        timer_result=opt_res,
        context={
            "session_minutes": episode_focused_mins,
            "planned_minutes": effective_planned_mins,
            "current_domain": domain,
            "current_category": current_category
        },
        feedback_summary=feedback_sum
    )

    if stop_reminders_flag == 1:
        dec_res["should_intervene"] = False
        dec_res["should_notify"] = False
        dec_res["should_overlay"] = False
        dec_res["suppression_reason"] = "stop_reminders"
        dec_res["friction_type"] = "NONE"

    sessions_repo.update_session_outcome(
        session_id=session_id,
        user_id=user_id,
        actual_focused_minutes=episode_focused_mins,
        intended_minutes=effective_planned_mins,
        optimized_target=opt_res.get("optimized_target"),
        user_action=None
    )

    solver_status = opt_res.get("solver_status", "")
    is_optimized  = solver_status == "OPTIMIZED"

    _status_map = {
        "OPTIMIZED":            dec_res.get("usage_status", "WITHIN_LIMIT"),
        "LEARNING":             "CALIBRATING",
        "USER_OVERRIDE":        "USER_OVERRIDE",
        "NO_TIMER":             "NO_TIMER",
        "TRACKING_UNRELIABLE":  "TRACKING_UNRELIABLE",
        "NO_FEASIBLE_SOLUTION": "OVER_LIMIT",
    }
    usage_status = _status_map.get(solver_status, dec_res.get("usage_status", solver_status))
    if session_status == "NO_PLAN":
        usage_status = "NO_PLAN"
    elif session_status == "OVER_PLAN":
        usage_status = "OVER_PLAN"

    return {
        "session_id":                     session_id,
        "episode_id":                     episode_id,
        "domain":                         domain,
        "technical_session_focused_minutes": focused_mins,
        "focused_minutes":                episode_focused_mins,
        "episode_focused_minutes":        episode_focused_mins,
        "used_minutes":                   episode_focused_mins,
        "original_intended_minutes":      original_intended_mins,
        "extension_minutes":              extension_mins,
        "effective_planned_minutes":      effective_planned_mins,
        "planned_minutes":                planned_mins_acc,
        "unplanned_minutes":              unplanned_mins,
        "unknown_minutes":                unknown_mins,
        "classification":                 "unknown" if session_status == "NO_PLAN" else purpose,
        "session_status":                 session_status,
        "intent": {
            "episode_id":                 episode_id,
            "purpose":                    purpose,
            "original_intended_minutes":  original_intended_mins,
            "extension_minutes":          extension_mins,
            "effective_planned_minutes":  effective_planned_mins,
            "timer_mode":                 timer_mode,
            "episode_status":             "ACTIVE" if session_status != "NO_PLAN" else "NO_PLAN"
        },
        "suppression_reason":            dec_res.get("suppression_reason"),
        "recommended_remaining":          remaining_mins if session_status != "NO_PLAN" else None,
        "recommended_remaining_minutes": remaining_mins if session_status != "NO_PLAN" else None,
        "recommended_additional_minutes": remaining_mins if session_status != "NO_PLAN" else None,
        "overuse_gap_minutes":            overuse_gap,
        "optimized_target":               opt_res.get("optimized_target"),
        "optimized_total_candidate":      opt_res.get("optimized_target"),
        "decision_id":                    dec_res.get("decision_id"),
        "should_intervene":               dec_res["should_intervene"],
        "should_notify":                  dec_res.get("should_notify", False),
        "should_overlay":                 dec_res.get("should_overlay", False),
        "friction_type":                  dec_res["friction_type"],
        "intervention_type":              dec_res["intervention_type"],
        "decision_reason":                dec_res["decision_reason"],
        "message":                        dec_res.get("message", ""),
        "usage_status":                   usage_status,
        "timer_source":                   "SESSION_OPTIMIZATION_ENGINE",
        "optimization_status":            solver_status,
        "is_optimized_target":            is_optimized,
        "cross_domain_allowance":         cross_domain_allowance,
        "substitution_status":            cross_domain_ctx["site_substitution_status"],
    }

@app.post("/sessions/{session_id}/action")
def record_session_action(session_id: str, req: ActionRequest):
    session = intent_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    user_id      = session["user_id"]
    actual_mins  = usage_tracker.calculate_focused_minutes(session_id)

    if req.action == "extend_5":
        sessions_repo.add_extension_minutes(session_id, 5.0)
        session = intent_service.get_session(session_id)
    elif req.action == "stop_reminders":
        sessions_repo.set_stop_reminders_for_session(session_id)
    elif req.action == "finish":
        sessions_repo.end_intent_episode_for_session(session_id, reason="finished")
        sessions_repo.set_unfocused_timestamp(session_id)

    intent       = session.get("intent") or {}
    original_intended = intent.get("intended_minutes")
    extension_mins = float(intent.get("extension_minutes", 0.0) or 0.0)
    effective_planned = (float(original_intended) + extension_mins) if original_intended is not None else None
    remaining_mins = max(0.0, round(effective_planned - actual_mins, 2)) if effective_planned is not None else None
    overuse_gap = max(0.0, round(actual_mins - effective_planned, 2)) if effective_planned is not None else 0.0

    session_context = {
        "domain":                 session.get("domain", "unknown"),
        "purpose":                intent.get("purpose", "unknown"),
        "planned_minutes":        effective_planned,
        "actual_focused_minutes": actual_mins,
        "optimized_target":       None,
        "task_completion":        req.task_completion,
        "time_sufficient":        req.time_sufficient,
    }
    latest_opt = opt_repo.get_latest_run(session_id)
    if latest_opt:
        session_context["optimized_target"] = latest_opt.get("optimized_target")

    fb_event = feedback_service.record_action(
        session_id=session_id,
        user_id=user_id,
        action=req.action,
        task_completion=req.task_completion,
        time_sufficient=req.time_sufficient,
        session_context=session_context,
    )

    sessions_repo.update_session_outcome(
        session_id=session_id,
        user_id=user_id,
        actual_focused_minutes=actual_mins,
        intended_minutes=effective_planned,
        user_action=req.action
    )

    return {
        "status": "success",
        "event": fb_event,
        "session_id": session_id,
        "original_intended_minutes": original_intended,
        "extension_minutes": extension_mins,
        "effective_planned_minutes": effective_planned,
        "planned_minutes": effective_planned,
        "used_minutes": actual_mins,
        "remaining_minutes": remaining_mins,
        "overuse_gap_minutes": overuse_gap
    }

@app.post("/sessions/{session_id}/end")
def end_session(session_id: str):
    session = intent_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session ended or not found")
    return {"status": "ended", "session_id": session_id}

@app.post("/jitai/delivery-trace")
def record_delivery_trace(req: DeliveryTraceRequest):
    trace = delivery_repo.record_trace(
        decision_id=req.decision_id,
        session_id=req.session_id,
        episode_id=req.episode_id,
        user_id=req.user_id,
        domain=req.domain,
        channel=req.channel,
        requested_channel=req.requested_channel,
        fallback_channel=req.fallback_channel,
        intervention_preserved=req.intervention_preserved or False,
        should_notify=req.should_notify,
        should_overlay=req.should_overlay,
        eligible=req.eligible,
        attempted_at_utc=req.attempted_at_utc,
        delivery_status=req.delivery_status,
        chrome_notification_id=req.chrome_notification_id,
        failure_reason=req.failure_reason,
        cooldown_source=req.cooldown_source,
        next_eligible_at=req.next_eligible_at
    )
    return {"status": "success", "trace": trace}

@app.get("/health")
@app.get("/dashboard/debug/health")
def get_debug_health():
    import subprocess
    git_commit = "f4aa05e"
    try:
        git_commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=str(PROJECT_ROOT), text=True).strip()
    except Exception:
        pass

    from app.core.config import DB_PATH
    return {
        "status": "ok",
        "app_version": "2.0.0",
        "git_commit": git_commit,
        "commit_build_id": git_commit,
        "schema_version": 1,
        "runtime_database_path": str(DB_PATH),
        "canonical_pipeline_version": "2.0.0"
    }

@app.get("/dashboard/{user_id}/summary")
def get_user_summary(user_id: str, local_tz: str = "UTC"):
    today_str = local_date_for_timezone(local_tz)
    today_rollups = rollups_repo.get_user_rollups(user_id, days=1)

    active_usage_mins = sum(r.get("focused_minutes", 0.0) for r in today_rollups if r.get("local_date") == today_str)
    unplanned_mins = sum(r.get("unplanned_minutes", 0.0) for r in today_rollups if r.get("local_date") == today_str)
    unknown_mins = sum(r.get("unknown_minutes", 0.0) for r in today_rollups if r.get("local_date") == today_str)

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT e.intended_minutes, e.original_intended_minutes, e.extension_minutes, e.timer_mode
               FROM technical_sessions t
               JOIN intent_episodes e ON t.episode_id = e.episode_id
               WHERE t.user_id = ? AND e.status = 'active'
               ORDER BY t.rowid DESC LIMIT 1""",
            (user_id,)
        )
        row = cur.fetchone()
        if row and row["timer_mode"] != "no_timer" and row["intended_minutes"] is not None:
            orig_m = float(row["original_intended_minutes"] if row["original_intended_minutes"] is not None else row["intended_minutes"])
            ext_m = float(row["extension_minutes"] or 0.0)
            effective_planned_mins = orig_m + ext_m
        else:
            effective_planned_mins = None
    finally:
        conn.close()

    if effective_planned_mins is not None and effective_planned_mins > 0:
        planned_mins = min(active_usage_mins, effective_planned_mins)
        remaining_mins = max(0.0, effective_planned_mins - active_usage_mins)
        unplanned_mins = max(0.0, active_usage_mins - effective_planned_mins)
    else:
        planned_mins = sum(r.get("planned_minutes", 0.0) for r in today_rollups if r.get("local_date") == today_str)
        effective_planned_mins = None
        remaining_mins = None

    hist_rollups = rollups_repo.get_user_rollups(user_id, days=14)
    distinct_dates = sorted(list(set(r["local_date"] for r in hist_rollups if r.get("local_date"))))

    if len(distinct_dates) < 3:
        status = "INSUFFICIENT_DATA"
        weekly_progress = None
    else:
        mid = len(distinct_dates) // 2
        baseline_dates = set(distinct_dates[:mid])
        current_dates = set(distinct_dates[mid:])
        baseline_unplanned = sum(r.get("unplanned_minutes", 0.0) for r in hist_rollups if r.get("local_date") in baseline_dates)
        current_unplanned = sum(r.get("unplanned_minutes", 0.0) for r in hist_rollups if r.get("local_date") in current_dates)
        eval_res = outcome_evaluator.evaluate(
            baseline_unplanned_minutes=baseline_unplanned,
            current_unplanned_minutes=current_unplanned,
            sample_count=len(distinct_dates)
        )
        status = eval_res["status"]
        weekly_progress = eval_res.get("unplanned_usage_reduction")

    return {
        "user_id": user_id,
        "local_date": today_str,
        "active_usage_minutes": round(active_usage_mins, 1),
        "planned_minutes": round(planned_mins, 1),
        "effective_planned_minutes": round(effective_planned_mins, 1) if effective_planned_mins is not None else None,
        "remaining_minutes": round(remaining_mins, 1) if remaining_mins is not None else None,
        "unplanned_overuse_minutes": round(unplanned_mins, 1),
        "unknown_minutes": round(unknown_mins, 1),
        "weekly_progress": weekly_progress,
        "status": status
    }

@app.get("/dashboard/{user_id}/history")
def get_user_history(user_id: str, days: int = 7):
    rollups = rollups_repo.get_user_rollups(user_id, days=days)
    grouped: Dict[str, Dict[str, Any]] = {}
    for r in rollups:
        d_str = r.get("local_date")
        if not d_str:
            continue
        if d_str not in grouped:
            grouped[d_str] = {
                "date": d_str,
                "focused_minutes": 0.0,
                "planned_minutes": 0.0,
                "unplanned_minutes": 0.0,
                "unknown_minutes": 0.0
            }
        grouped[d_str]["focused_minutes"] += float(r.get("focused_minutes", 0.0))
        grouped[d_str]["planned_minutes"] += float(r.get("planned_minutes", 0.0))
        grouped[d_str]["unplanned_minutes"] += float(r.get("unplanned_minutes", 0.0))
        grouped[d_str]["unknown_minutes"] += float(r.get("unknown_minutes", 0.0))

    history_list = []
    for d in sorted(grouped.keys(), reverse=True):
        item = grouped[d]
        f_min = round(item["focused_minutes"], 1)
        p_min = round(min(f_min, item["planned_minutes"]), 1)
        unp_min = round(item["unplanned_minutes"], 1)
        unk_min = round(item["unknown_minutes"], 1)
        history_list.append({
            "date": d,
            "focused_minutes": f_min,
            "planned_minutes": p_min,
            "unplanned_minutes": unp_min,
            "unknown_minutes": unk_min
        })

    return {"user_id": user_id, "history": history_list}

@app.get("/dashboard/{user_id}/platforms")
def get_user_platforms(user_id: str, local_tz: str = "UTC"):
    today_str = local_date_for_timezone(local_tz)
    rollups = rollups_repo.get_user_rollups(user_id, days=1)
    platforms: Dict[str, float] = {}
    for r in rollups:
        if r.get("local_date") == today_str:
            d = r.get("domain")
            if d:
                platforms[d] = round(platforms.get(d, 0.0) + float(r.get("focused_minutes", 0.0)), 1)
    return {"user_id": user_id, "local_date": today_str, "platforms": platforms}

@app.get("/dashboard/{user_id}/current")
def get_user_current_runtime_state(user_id: str):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT t.session_id, t.episode_id, t.domain, e.purpose, e.intended_minutes
               FROM technical_sessions t
               LEFT JOIN intent_episodes e ON t.episode_id = e.episode_id
               WHERE t.user_id = ?
               ORDER BY t.rowid DESC LIMIT 1""",
            (user_id,)
        )
        sess_row = cur.fetchone()
        current_session = None
        current_sid = None
        current_epid = None

        if sess_row:
            sess_dict = dict(sess_row)
            current_sid = sess_dict["session_id"]
            current_epid = sess_dict["episode_id"]
            ep_focused_mins = sessions_repo.get_episode_focused_minutes(current_epid) if current_epid else usage_tracker.calculate_focused_minutes(current_sid)
            current_session = {
                "session_id": current_sid,
                "episode_id": current_epid,
                "domain": sess_dict["domain"],
                "purpose": sess_dict.get("purpose") or "unknown",
                "episode_focused_minutes": ep_focused_mins
            }

        latest_intervention = None
        if current_session:
            cur.execute(
                """SELECT session_id, user_id, optimized_target, recommended_remaining, solver_status, created_at_utc
                   FROM optimization_runs
                   WHERE user_id = ?
                   ORDER BY rowid DESC LIMIT 1""",
                (user_id,)
            )
            opt_row = cur.fetchone()
            if opt_row:
                opt_dict = dict(opt_row)
                opt_sid = opt_dict.get("session_id")

                opt_epid = None
                if opt_sid:
                    cur.execute("SELECT episode_id FROM technical_sessions WHERE session_id = ?", (opt_sid,))
                    ep_row = cur.fetchone()
                    if ep_row:
                        opt_epid = ep_row[0]

                matches_session = (opt_sid and current_sid and opt_sid == current_sid)
                matches_episode = (opt_epid and current_epid and opt_epid == current_epid)

                if matches_session or matches_episode:
                    latest_intervention = opt_dict

        return {
            "current_session": current_session,
            "latest_intervention": latest_intervention
        }
    finally:
        conn.close()

@app.get("/dashboard/{user_id}/goal")
def get_user_goal_summary(user_id: str):
    goal = goals_repo.get_goal(user_id)
    if not goal:
        goal = goals_repo.upsert_goal(user_id=user_id, selected_domains=["youtube.com", "instagram.com"])
    return goal


# ==========================================
# 2. RESEARCH ENDPOINTS
# ==========================================

@app.get("/dashboard/research/{user_id}/optimization")
def get_research_optimization(user_id: str):
    """Research route: full optimization run history with candidates, constraints, cross-domain context."""
    runs = opt_repo.get_user_runs(user_id, limit=10)
    temptation_formula = {
        "formula": "T = w1*overrun + w2*reopen + w3*uninterrupted + w4*habitual + w5*context + w6*switching + w7*historical_overrun",
        "weights": SYSTEM_PARAMETERS["temptation_weights"]["value"],
        "weight_source": SYSTEM_PARAMETERS["temptation_weights"]["source"],
        "configuration_version": CONFIG_VERSION,
    }
    cross_domain_ctx = cross_domain_service.get_cross_domain_context(
        user_id=user_id, current_domain="", days=7
    )
    return {
        "user_id":             user_id,
        "optimization_runs":   runs,
        "temptation_formula":  temptation_formula,
        "cross_domain_context": cross_domain_ctx,
        "limitations": [
            "TemptationEstimator uses VERSIONED_DEFAULT weights — not trained on labelled data.",
            "PersonalAdaptationService uses EMA; structural parameters require longitudinal data.",
            "Effectiveness requires baseline-vs-intervention data from real extension usage.",
        ],
    }

@app.get("/dashboard/research/{user_id}/parameters")
def get_research_parameters(user_id: str):
    """Research route: all personal parameters with full provenance."""
    params = params_repo.get_all_user_parameters(user_id)
    return {
        "user_id":    user_id,
        "parameters": params,
        "system_parameters": {
            k: {"value": v["value"], "source": v["source"], "description": v["description"]}
            for k, v in SYSTEM_PARAMETERS.items()
        },
        "configuration_version": CONFIG_VERSION,
    }

@app.get("/dashboard/research/{user_id}/outcomes")
def get_research_outcomes(user_id: str):
    """Research route: realized vs targeted reduction with substitution context."""
    rollups = rollups_repo.get_user_rollups(user_id, days=30)
    distinct_dates = sorted(list(set(r["local_date"] for r in rollups if r.get("local_date"))))
    total_unplanned = sum(r.get("unplanned_minutes", 0) for r in rollups)
    total_focused   = sum(r.get("focused_minutes", 0)   for r in rollups)
    goal = goals_repo.get_goal(user_id)
    target_reduction_pct = float(goal.get("target_reduction_percent", 20.0)) if goal else 20.0

    if len(distinct_dates) < 3:
        eval_res = {
            "status": "INSUFFICIENT_DATA",
            "unplanned_usage_reduction": None,
            "message": "Insufficient baseline evidence to evaluate progress.",
            "window_dates": distinct_dates,
            "sample_counts": len(distinct_dates),
            "baseline_value": None,
            "comparison_value": total_unplanned,
            "calculation": "None (insufficient historical baseline window data)"
        }
    else:
        mid = len(distinct_dates) // 2
        baseline_dates = set(distinct_dates[:mid])
        current_dates = set(distinct_dates[mid:])
        baseline_unplanned = sum(r.get("unplanned_minutes", 0) for r in rollups if r.get("local_date") in baseline_dates)
        current_unplanned = sum(r.get("unplanned_minutes", 0) for r in rollups if r.get("local_date") in current_dates)
        eval_res = outcome_evaluator.evaluate(
            baseline_unplanned_minutes=baseline_unplanned,
            current_unplanned_minutes=current_unplanned,
            sample_count=len(distinct_dates)
        )
        eval_res["window_dates"] = distinct_dates
        eval_res["sample_counts"] = len(distinct_dates)
        eval_res["baseline_value"] = baseline_unplanned
        eval_res["comparison_value"] = current_unplanned
        eval_res["calculation"] = f"({baseline_unplanned:.2f} - {current_unplanned:.2f}) / {baseline_unplanned + 1e-5:.2f}"

    cross_domain_ctx = cross_domain_service.get_cross_domain_context(
        user_id=user_id, current_domain="", days=30
    )
    return {
        "user_id":              user_id,
        "evaluation":           eval_res,
        "targeted_reduction_pct": target_reduction_pct,
        "total_focused_minutes":  round(total_focused, 2),
        "total_unplanned_minutes": round(total_unplanned, 2),
        "cross_domain_context":   cross_domain_ctx,
        "effectiveness_caveat":   "Behavioral effectiveness requires baseline-vs-intervention data from real extension usage.",
    }
    cross_domain_ctx = cross_domain_service.get_cross_domain_context(
        user_id=user_id, current_domain="", days=30
    )
    return {
        "user_id":              user_id,
        "evaluation":           eval_res,
        "targeted_reduction_pct": target_reduction_pct,
        "total_focused_minutes":  round(total_focused, 2),
        "total_unplanned_minutes": round(total_unplanned, 2),
        "cross_domain_context":   cross_domain_ctx,
        "effectiveness_caveat":   "Behavioral effectiveness requires baseline-vs-intervention data from real extension usage.",
    }


# ==========================================
# 3. DEBUG ENDPOINTS
# ==========================================

@app.get("/dashboard/debug/events")
def get_debug_events(user_id: str = "local_user"):
    fb = feedback_repo.get_user_feedback_summary(user_id)
    return {"user_id": user_id, "feedback_summary": fb}

@app.get("/dashboard/debug/cooldowns")
def get_debug_cooldowns(user_id: str = "local_user"):
    return {"user_id": user_id, "cooldown_active": False, "remaining_seconds": 0}


# ==========================================
# 4. LEGACY COMPATIBILITY ROUTING
# ==========================================

@app.post("/habitguard/custom/intervention")
def get_custom_intervention(req: LegacyCustomUsageRequest):
    timer_result     = structural_timer_engine.compute_timer(req.usage_history_minutes)
    context_dict     = req.context.model_dump() if req.context else {}
    feedback_summary = feedback_service.get_summary(user_id=req.user_id)

    response = decision_engine.decide(
        timer_result=timer_result,
        context=context_dict,
        feedback_summary=feedback_summary
    )

    # Fix 5 — legacy timer label
    return {
        "model_type":          "personalized_structural_timer",
        "user_id":             req.user_id,
        "input_usage_history": req.usage_history_minutes,
        "context_used":        context_dict,
        "structural_timer":    timer_result,
        "timer_source":        "STRUCTURAL_TIMER_LEGACY",
        "optimization_status": "LEGACY_FALLBACK",
        "is_optimized_target": False,
        **response
    }

@app.get("/habitguard/user/{user_id}/intervention")
def get_user_intervention(user_id: str):
    summary = habitguard_service.get_user_daily_summary(user_id)
    if summary.get("status") == "ANALYTICS_DATA_UNAVAILABLE":
        return summary
    if "error" in summary:
        raise HTTPException(status_code=404, detail=summary["error"])
    daily_history    = summary.get("daily_usage_history", [])
    timer_result     = structural_timer_engine.compute_timer(daily_history)
    feedback_summary = feedback_service.get_summary(user_id=user_id)
    dec = decision_engine.decide(
        timer_result=timer_result,
        context={},
        feedback_summary=feedback_summary
    )
    dec["user_id"]             = user_id
    dec["timer_source"]        = "STRUCTURAL_TIMER_LEGACY"
    dec["optimization_status"] = "LEGACY_FALLBACK"
    dec["is_optimized_target"] = False
    return dec


@app.get("/habitguard/user/{user_id}/summary")
def get_legacy_user_summary(user_id: str):
    res = habitguard_service.get_user_daily_summary(user_id)
    if res.get("status") == "ANALYTICS_DATA_UNAVAILABLE":
        return res
    if "error" in res:
        raise HTTPException(status_code=404, detail=res["error"])
    return res

@app.get("/habitguard/user/{user_id}/apps/{app_name}/summary")
def get_legacy_app_summary(user_id: str, app_name: str):
    res = habitguard_service.get_user_app_summary(user_id, app_name)
    if res.get("status") == "ANALYTICS_DATA_UNAVAILABLE":
        return res
    if "error" in res:
        raise HTTPException(status_code=404, detail=res["error"])
    return res