from app.services.dataset_service import DatasetService
from app.services.addiction_engine import AddictionEngine
from app.services.dynamic_limit_engine import DynamicLimitEngine


CSV_PATH = "../data/processed/cleaned_screen_time.csv"


def test_daily_usage_pipeline():
    dataset_service = DatasetService(CSV_PATH)
    df = dataset_service.load_data()

    sample_user = str(df["user_id"].iloc[0])

    daily_usage_history = dataset_service.get_user_daily_total_usage(
        df,
        sample_user
    )

    assert len(daily_usage_history) > 0
    assert all(usage >= 0 for usage in daily_usage_history)

    addiction_engine = AddictionEngine()
    limit_engine = DynamicLimitEngine()

    scores = addiction_engine.calculate_scores(daily_usage_history)
    current_score = addiction_engine.current_score(daily_usage_history)
    score_level = addiction_engine.score_level(current_score)
    recommended_limit = limit_engine.recommend_limit(current_score)

    assert len(scores) == len(daily_usage_history)
    assert current_score == scores[-1]
    assert score_level in ("LOW", "MODERATE", "HIGH", "SEVERE")
    assert recommended_limit > 0

    friction = limit_engine.friction_action(
        usage_today=daily_usage_history[-1],
        recommended_limit=recommended_limit
    )

    assert friction["level"] in (
        "NONE",
        "SOFT_WARNING",
        "WARNING",
        "LIGHT_COOLDOWN",
        "MEDIUM_COOLDOWN",
        "STRONG_COOLDOWN"
    )
    assert isinstance(friction["message"], str)
    assert friction["cooldown_seconds"] >= 0