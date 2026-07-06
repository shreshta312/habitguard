from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
from app.services.habitguard_service import HabitGuardService
from app.services.dataset_service import DatasetService
from app.services.anomaly_service import AnomalyService
from app.services.risk_service import RiskService
from app.services.segment_service import SegmentService
from app.services.structural_timer_engine import StructuralTimerEngine
from app.services.decision_engine import DecisionEngine
from app.api.feedback import router as feedback_router
from app.services.feedback_service import feedback_service
from app.api.usage import router as usage_router

app = FastAPI(
    title="HabitGuard API",
    description="Backend API for addiction score, dynamic limits, and usage monitoring",
    version="1.0.0"  
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(feedback_router)
app.include_router(usage_router)

CSV_PATH = "../data/processed/cleaned_screen_time.csv"

habitguard_service = HabitGuardService(CSV_PATH)
dataset_service = DatasetService(CSV_PATH)
anomaly_service = AnomalyService()
risk_service = RiskService()
segment_service = SegmentService()
structural_timer_engine = StructuralTimerEngine()
decision_engine = DecisionEngine()


# Single cached DataFrame for dataset-exploration endpoints (/users, /apps,
# /habitguard/user/*). Loaded once on first request via _get_dataset_df().
# HabitGuardService uses its own identical cache via _get_df().
# The two caches hold the same data — this is intentional: dataset_service
# is stateless (no _df attribute), so we cache here at the app layer.
_dataset_df = None


def _get_dataset_df():
    global _dataset_df
    if _dataset_df is None:
        _dataset_df = dataset_service.load_data()
    return _dataset_df


class AnomalyRequest(BaseModel):
    screen_time_min: float
    launches: int
    interactions: int
    is_productive: int


class RiskRequest(BaseModel):
    age: float
    daily_screen_time_hours: float
    social_media_hours: float
    gaming_hours: float
    work_study_hours: float
    sleep_hours: float
    notifications_per_day: float
    app_opens_per_day: float
    weekend_screen_time: float
    stress_level: float
    academic_work_impact: float
    gender_male: float
    gender_other: float

class ContextRequest(BaseModel):
    current_domain: str | None = None
    current_category: str | None = None
    session_minutes: float | None = None
    top_domains: dict[str, float] | None = None
    timestamp: int | None = None


class CustomUsageRequest(BaseModel):
    user_id: str = "local_user"
    usage_history_minutes: list[float]
    context: ContextRequest | None = None


def _build_intervention_response(
    timer_result,
    context=None,
    extra_fields=None,
    user_id="local_user"
):
    """
    Delegates intervention decisions to DecisionEngine.

    StructuralTimerEngine computes the personalized timer.
    DecisionEngine decides how that timer should be translated into
    an intervention using live Chrome context and feedback history.
    """

    feedback_summary = feedback_service.get_summary(user_id=user_id)

    response = decision_engine.decide(
        timer_result=timer_result,
        context=context,
        feedback_summary=feedback_summary
    )

    if extra_fields:
        response = {**extra_fields, **response}

    return response

@app.get("/")
def home():
    return {
        "message": "HabitGuard API is running"
    }


@app.get("/users")
def get_users():
    users = dataset_service.get_all_users(_get_dataset_df())

    return {
        "total_users": len(users),
        "users": users
    }


@app.get("/apps")
def get_apps():
    apps = dataset_service.get_all_apps(_get_dataset_df())

    return {
        "total_apps": len(apps),
        "apps": apps
    }

@app.get("/habitguard/dashboard/{user_id}")
def get_dashboard_data(user_id: int):
    df = _get_dataset_df()

    user_df = df[df["user_id"].astype(str) == str(user_id)].copy()

    if user_df.empty:
        raise HTTPException(
            status_code=404,
            detail="User not found or no usage data available"
        )

    user_df["date"] = pd.to_datetime(user_df["date"])

    daily_usage_df = (
        user_df.groupby("date")["screen_time_min"]
        .sum()
        .reset_index()
        .sort_values("date")
    )

    daily_usage_history = daily_usage_df["screen_time_min"].tolist()

    if len(daily_usage_history) == 0:
        raise HTTPException(
            status_code=404,
            detail="No daily usage history available"
        )

    latest_date = daily_usage_df["date"].max()
    today_df = user_df[user_df["date"] == latest_date]

    today_usage_minutes = round(float(daily_usage_history[-1]), 2)

    weekly_usage = []
    for _, row in daily_usage_df.tail(7).iterrows():
        weekly_usage.append({
            "date": row["date"].strftime("%Y-%m-%d"),
            "day": row["date"].strftime("%a"),
            "minutes": round(float(row["screen_time_min"]), 2)
        })

    top_apps_df = (
        today_df.groupby("app_name")["screen_time_min"]
        .sum()
        .reset_index()
        .sort_values("screen_time_min", ascending=False)
        .head(5)
    )

    top_apps = [
        {
            "app_name": row["app_name"],
            "minutes": round(float(row["screen_time_min"]), 2)
        }
        for _, row in top_apps_df.iterrows()
    ]

    category_usage_df = (
        today_df.groupby("category")["screen_time_min"]
        .sum()
        .reset_index()
        .sort_values("screen_time_min", ascending=False)
    )

    category_usage = [
        {
            "category": row["category"],
            "minutes": round(float(row["screen_time_min"]), 2)
        }
        for _, row in category_usage_df.iterrows()
    ]

    productive_minutes = round(
        float(today_df[today_df["is_productive"] == 1]["screen_time_min"].sum()),
        2
    )

    distracting_minutes = round(
        float(today_df[today_df["is_productive"] == 0]["screen_time_min"].sum()),
        2
    )

    timer_result = structural_timer_engine.get_structural_timer_summary(
        usage_history_minutes=daily_usage_history
    )

    legacy_summary = habitguard_service.get_user_daily_summary(user_id)

    launches_today = int(today_df["launches"].sum())
    interactions_today = int(today_df["interactions"].sum())

    is_productive_today = 1 if productive_minutes >= distracting_minutes else 0

    anomaly_result = anomaly_service.detect_anomaly(
        screen_time_min=today_usage_minutes,
        launches=launches_today,
        interactions=interactions_today,
        is_productive=is_productive_today
    )

    if len(daily_usage_history) >= 3:
        forecast_minutes = round(
            float(sum(daily_usage_history[-3:]) / 3),
            2
        )
        forecast_source = "temporary_3_day_average_until_forecaster_service_is_connected"
    else:
        forecast_minutes = today_usage_minutes
        forecast_source = "not_enough_history_using_today_usage"

    return {
        "user_id": user_id,
        "date": latest_date.strftime("%Y-%m-%d"),

        "today_usage_minutes": today_usage_minutes,
        "productive_minutes": productive_minutes,
        "distracting_minutes": distracting_minutes,

        "risk": {
            "source": "legacy_addiction_score_summary",
            "score": legacy_summary.get("current_score"),
            "level": legacy_summary.get("score_level"),
            "note": "This is the legacy score. The ML risk classifier needs profile features before it can be used here."
        },

        "anomaly": anomaly_result,

        "forecast": {
            "forecast_minutes": forecast_minutes,
            "source": forecast_source,
            "note": "Next step is to connect the saved usage_forecaster.pkl model properly."
        },

        "structural_timer": timer_result,

        "weekly_usage": weekly_usage,
        "top_apps": top_apps,
        "category_usage": category_usage,

        "dashboard_cards": {
           "total_usage": today_usage_minutes,
            "risk_level": legacy_summary.get("score_level"),
            "recommended_timer": timer_result.get("recommended_timer_minutes"),
            "anomaly_status": anomaly_result.get(
               "result",
             anomaly_result.get("status", anomaly_result.get("prediction", "UNKNOWN"))
            ),
         "forecast_minutes": forecast_minutes
        }
    }


@app.get("/users/{user_id}/apps")
def get_user_apps(user_id: int):
    apps = dataset_service.get_user_apps(_get_dataset_df(), user_id)

    return {
        "user_id": user_id,
        "total_apps": len(apps),
        "apps": apps
    }


@app.get("/users/{user_id}/summary")
def get_user_summary(user_id: int):
    return habitguard_service.get_user_daily_summary(user_id)


@app.get("/users/{user_id}/apps/{app_name}/summary")
def get_user_app_summary(user_id: int, app_name: str):
    return habitguard_service.get_user_app_summary(user_id, app_name)


@app.post("/anomaly/check")
def check_anomaly(request: AnomalyRequest):
    return anomaly_service.detect_anomaly(
        screen_time_min=request.screen_time_min,
        launches=request.launches,
        interactions=request.interactions,
        is_productive=request.is_productive
    )


@app.post("/risk/predict")
def predict_risk(request: RiskRequest):
    features = {
        "age": request.age,
        "daily_screen_time_hours": request.daily_screen_time_hours,
        "social_media_hours": request.social_media_hours,
        "gaming_hours": request.gaming_hours,
        "work_study_hours": request.work_study_hours,
        "sleep_hours": request.sleep_hours,
        "notifications_per_day": request.notifications_per_day,
        "app_opens_per_day": request.app_opens_per_day,
        "weekend_screen_time": request.weekend_screen_time,
        "stress_level": request.stress_level,
        "academic_work_impact": request.academic_work_impact,
        "gender_male": request.gender_male,
        "gender_other": request.gender_other,
    }

    return risk_service.predict_risk(features)


@app.post("/segment/predict")
def predict_segment(request: RiskRequest):
    features = {
        "age": request.age,
        "daily_screen_time_hours": request.daily_screen_time_hours,
        "social_media_hours": request.social_media_hours,
        "gaming_hours": request.gaming_hours,
        "work_study_hours": request.work_study_hours,
        "sleep_hours": request.sleep_hours,
        "notifications_per_day": request.notifications_per_day,
        "app_opens_per_day": request.app_opens_per_day,
        "weekend_screen_time": request.weekend_screen_time,
        "stress_level": request.stress_level,
        "academic_work_impact": request.academic_work_impact,
        "gender_male": request.gender_male,
        "gender_other": request.gender_other,
    }

    return segment_service.predict_segment(features)


@app.get("/habitguard/user/{user_id}/timer")
def get_structural_timer(user_id: int):
    # Use daily totals, not raw per-row screen_time_min values.
    # A user with multiple apps per day would otherwise produce multiple
    # entries per day, which the engine would treat as separate days.
    usage_history = dataset_service.get_user_daily_total_usage(_get_dataset_df(), user_id)

    if len(usage_history) == 0:
        raise HTTPException(
         status_code=404,
           detail="User not found or no usage data available"
        )

    result = structural_timer_engine.get_structural_timer_summary(
        usage_history_minutes=usage_history
    )

    return {
        "user_id": user_id,
        "structural_timer": result
    }


@app.get("/habitguard/user/{user_id}/intervention")
def get_user_intervention(user_id: int):
    # Use daily totals for the same reason as the timer endpoint above.
    usage_history = dataset_service.get_user_daily_total_usage(
        _get_dataset_df(),
        user_id
    )

    if len(usage_history) == 0:
       raise HTTPException(
           status_code=404,
           detail="User not found or no usage data available"
        )

    timer_result = structural_timer_engine.get_structural_timer_summary(
        usage_history_minutes=usage_history
    )

    if timer_result.get("mode") == "CALIBRATION":
        return {
            "user_id": user_id,
            "mode": "CALIBRATION",
            "timer_active": False,
            "usage_status": "COLLECTING_BASELINE",
            "friction_type": "NONE",
            "recommended_timer_minutes": None,
            "intervention_type": "NONE",
            "should_intervene": False,
            "decision_reason": "HabitGuard is still collecting baseline data.",
            "message": timer_result.get("message")
        }

    return _build_intervention_response(
        timer_result,
        extra_fields={"user_id": user_id},
        user_id=str(user_id)
    )



@app.post("/habitguard/custom/intervention")
def get_custom_intervention(request: CustomUsageRequest):
    usage_history = request.usage_history_minutes
    context = request.context.model_dump() if request.context else None

    if len(usage_history) == 0:
        return {
            "mode": "NO_DATA",
            "timer_active": False,
            "usage_status": "NO_USAGE_HISTORY",
            "friction_type": "NONE",
            "recommended_timer_minutes": None,
            "intervention_type": "NONE",
            "should_intervene": False,
            "decision_reason": "No usage history is available yet.",
            "message": "Browse for a few minutes so HabitGuard can start tracking usage.",
            "context_used": context,
            "error": "No usage history available"
        }

    timer_result = structural_timer_engine.get_structural_timer_summary(
        usage_history_minutes=usage_history
    )

    if timer_result.get("mode") == "CALIBRATION":
        return {
            "mode": "CALIBRATION",
            "timer_active": False,
            "usage_status": "COLLECTING_BASELINE",
            "friction_type": "NONE",
            "recommended_timer_minutes": None,
            "intervention_type": "NONE",
            "should_intervene": False,
            "decision_reason": "HabitGuard is still collecting baseline data.",
            "message": timer_result.get("message"),
            "context_used": context
        }

    return _build_intervention_response(
        timer_result,
        context=context,
        user_id=request.user_id
    )