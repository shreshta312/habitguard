from app.services.dataset_service import DatasetService
from app.services.addiction_engine import AddictionEngine
from app.services.dynamic_limit_engine import DynamicLimitEngine


csv_path = "../data/processed/cleaned_screen_time.csv"

dataset_service = DatasetService(csv_path)
df = dataset_service.load_data()

print("Dataset loaded successfully")
print("Rows:", len(df))
print("Users:", df["user_id"].nunique())
print("Apps:", df["app_name"].nunique())
print("Date range:", df["date"].min(), "to", df["date"].max())

sample_user = df["user_id"].iloc[0]

user_df = df[df["user_id"] == sample_user]

app_counts = user_df["app_name"].value_counts()
sample_app = app_counts.idxmax()

user_apps = dataset_service.get_user_apps(df, sample_user)

usage_history = dataset_service.get_user_app_usage(
    df,
    sample_user,
    sample_app
)

addiction_engine = AddictionEngine()
limit_engine = DynamicLimitEngine()

scores = addiction_engine.calculate_scores(usage_history)
current_score = addiction_engine.current_score(usage_history)
score_level = addiction_engine.score_level(current_score)
recommended_limit = limit_engine.recommend_limit(current_score)

print("\nSample User:", sample_user)
print("User Apps:", user_apps)
print("Selected App:", sample_app)
print("Usage History:", usage_history)
print("Addiction Scores:", scores)
print("Current Score:", current_score)
print("Score Level:", score_level)
print("Recommended Limit:", recommended_limit)