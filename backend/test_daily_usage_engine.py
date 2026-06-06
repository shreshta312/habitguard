from app.services.dataset_service import DatasetService
from app.services.addiction_engine import AddictionEngine
from app.services.dynamic_limit_engine import DynamicLimitEngine


csv_path = "../data/processed/cleaned_screen_time.csv"

dataset_service = DatasetService(csv_path)
df = dataset_service.load_data()

sample_user = df["user_id"].iloc[0]

daily_usage_history = dataset_service.get_user_daily_total_usage(
    df,
    sample_user
)

addiction_engine = AddictionEngine()
limit_engine = DynamicLimitEngine()

scores = addiction_engine.calculate_scores(daily_usage_history)
current_score = addiction_engine.current_score(daily_usage_history)
score_level = addiction_engine.score_level(current_score)
recommended_limit = limit_engine.recommend_limit(current_score)

friction = limit_engine.friction_action(
    usage_today=daily_usage_history[-1],
    recommended_limit=recommended_limit
)

print("Sample User:", sample_user)
print("Daily Total Usage History:", daily_usage_history)
print("Addiction Scores:", scores)
print("Current Score:", current_score)
print("Score Level:", score_level)
print("Recommended Limit:", recommended_limit)
print("Friction Action:", friction)