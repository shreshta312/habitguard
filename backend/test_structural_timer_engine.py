from app.services.dataset_service import DatasetService
from app.services.structural_timer_engine import StructuralTimerEngine


csv_path = "../data/processed/cleaned_screen_time.csv"

dataset_service = DatasetService(csv_path)
df = dataset_service.load_data()

sample_user = 1000

daily_usage_history = dataset_service.get_user_daily_total_usage(
    df,
    sample_user
)

engine = StructuralTimerEngine()

summary = engine.get_structural_timer_summary(daily_usage_history)

print("Structural Timer Summary")
print("------------------------")
print("User ID:", sample_user)
print("Usage History:", daily_usage_history)

print("\nBaseline Usage Minutes:", summary["baseline_usage_minutes"])
print("Baseline Usage Hours:", summary["baseline_usage_hours"])
print("Xi User:", summary["xi_user"])
print("Rho Paper:", summary["rho_paper"])
print("Rho Daily Reference:", summary["rho_daily_reference"])
print("Current Habit Stock:", summary["current_habit_stock"])

print("\nPredicted Natural Usage Minutes:", summary["predicted_natural_usage_minutes"])
print("Recommended Target Usage Minutes:", summary["recommended_target_usage_minutes"])
print("Recommended Timer Minutes:", summary["recommended_timer_minutes"])
print("Temptation Gap Minutes:", summary["temptation_gap_minutes"])
print("\nInterpretation:")
print(summary["interpretation"])