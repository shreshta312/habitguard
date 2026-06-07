from fastapi import FastAPI
from app.services.habitguard_service import HabitGuardService
from app.services.dataset_service import DatasetService
from pydantic import BaseModel
from app.services.anomaly_service import AnomalyService
from app.services.risk_service import RiskService
from app.services.segment_service import SegmentService

app = FastAPI(
    title="HabitGuard API",
    description="Backend API for addiction score, dynamic limits, and usage monitoring",
    version="1.0.0"
)

CSV_PATH = "../data/processed/cleaned_screen_time.csv"

habitguard_service = HabitGuardService(CSV_PATH)
dataset_service = DatasetService(CSV_PATH)
df = dataset_service.load_data()
anomaly_service = AnomalyService()
risk_service = RiskService()
segment_service = SegmentService()

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

@app.get("/")
def home():
    return {
        "message": "HabitGuard API is running"
    }


@app.get("/users")
def get_users():
    users = dataset_service.get_all_users(df)

    return {
        "total_users": len(users),
        "users": users
    }


@app.get("/apps")
def get_apps():
    apps = dataset_service.get_all_apps(df)

    return {
        "total_apps": len(apps),
        "apps": apps
    }


@app.get("/users/{user_id}/apps")
def get_user_apps(user_id: int):
    apps = dataset_service.get_user_apps(df, user_id)

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