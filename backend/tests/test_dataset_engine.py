from app.services.dataset_service import DatasetService
from app.services.addiction_engine import AddictionEngine
from app.services.dynamic_limit_engine import DynamicLimitEngine


CSV_PATH = "../data/processed/cleaned_screen_time.csv"


def test_dataset_loads_correctly():
    dataset_service = DatasetService(CSV_PATH)
    df = dataset_service.load_data()

    assert len(df) > 0
    assert df["user_id"].nunique() > 0
    assert df["app_name"].nunique() > 0
    assert df["date"].notna().all()
    assert df["screen_time_min"].notna().all()
    assert (df["screen_time_min"] >= 0).all()


def test_user_app_usage_pipeline():
    dataset_service = DatasetService(CSV_PATH)
    df = dataset_service.load_data()

    sample_user = str(df["user_id"].iloc[0])
    user_apps = dataset_service.get_user_apps(df, sample_user)

    assert len(user_apps) > 0

    sample_app = user_apps[0]

    usage_history = dataset_service.get_user_app_usage(
        df,
        sample_user,
        sample_app
    )

    assert len(usage_history) > 0
    assert all(usage >= 0 for usage in usage_history)

    addiction_engine = AddictionEngine()
    limit_engine = DynamicLimitEngine()

    scores = addiction_engine.calculate_scores(usage_history)
    current_score = addiction_engine.current_score(usage_history)
    score_level = addiction_engine.score_level(current_score)
    recommended_limit = limit_engine.recommend_limit(current_score)

    assert len(scores) == len(usage_history)
    assert current_score == scores[-1]
    assert score_level in ("LOW", "MODERATE", "HIGH", "SEVERE")
    assert recommended_limit > 0