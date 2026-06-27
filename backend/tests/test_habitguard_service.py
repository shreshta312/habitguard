from app.services.habitguard_service import HabitGuardService
from app.services.dataset_service import DatasetService


CSV_PATH = "../data/processed/cleaned_screen_time.csv"


def test_user_daily_summary():
    dataset_service = DatasetService(CSV_PATH)
    df = dataset_service.load_data()

    sample_user = int(df["user_id"].iloc[0])

    service = HabitGuardService(CSV_PATH)
    summary = service.get_user_daily_summary(user_id=sample_user)

    assert "error" not in summary
    assert summary["user_id"] == sample_user

    assert "daily_usage_history" in summary
    assert "addiction_scores" in summary
    assert "current_score" in summary
    assert "score_level" in summary
    assert "recommended_limit" in summary
    assert "today_usage" in summary
    assert "friction_action" in summary

    assert len(summary["daily_usage_history"]) > 0
    assert len(summary["addiction_scores"]) == len(summary["daily_usage_history"])
    assert summary["score_level"] in ("LOW", "MODERATE", "HIGH", "SEVERE")
    assert summary["recommended_limit"] > 0
    assert summary["today_usage"] == summary["daily_usage_history"][-1]

    assert "level" in summary["friction_action"]
    assert "message" in summary["friction_action"]
    assert "cooldown_seconds" in summary["friction_action"]


def test_missing_user_returns_error():
    service = HabitGuardService(CSV_PATH)

    summary = service.get_user_daily_summary(user_id=999999999)

    assert "error" in summary
    assert summary["user_id"] == 999999999


def test_user_app_summary():
    dataset_service = DatasetService(CSV_PATH)
    df = dataset_service.load_data()

    sample_user = int(df["user_id"].iloc[0])
    sample_app = dataset_service.get_user_apps(df, str(sample_user))[0]

    service = HabitGuardService(CSV_PATH)
    summary = service.get_user_app_summary(
        user_id=sample_user,
        app_name=sample_app
    )

    assert "error" not in summary
    assert summary["user_id"] == sample_user
    assert summary["app_name"].lower() == sample_app.lower()

    assert "usage_history" in summary
    assert "addiction_scores" in summary
    assert "current_score" in summary
    assert "score_level" in summary
    assert "recommended_limit" in summary
    assert "today_usage" in summary
    assert "friction_action" in summary

    assert len(summary["usage_history"]) > 0
    assert len(summary["addiction_scores"]) == len(summary["usage_history"])
    assert summary["score_level"] in ("LOW", "MODERATE", "HIGH", "SEVERE")
    assert summary["recommended_limit"] > 0
    assert summary["today_usage"] == summary["usage_history"][-1]