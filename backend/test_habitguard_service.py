from app.services.habitguard_service import HabitGuardService


csv_path = "../data/processed/cleaned_screen_time.csv"

service = HabitGuardService(csv_path)

summary = service.get_user_daily_summary(user_id=1000)

print("HabitGuard User Summary")
print("-----------------------")
print("User ID:", summary["user_id"])
print("Today Usage:", summary["today_usage"])
print("Current Addiction Score:", summary["current_score"])
print("Score Level:", summary["score_level"])
print("Recommended Limit:", summary["recommended_limit"])
print("Friction Action:", summary["friction_action"])

print("\nUsage History:")
print(summary["daily_usage_history"])

print("\nAddiction Score History:")
print(summary["addiction_scores"])