from app.services.addiction_engine import AddictionEngine
from app.services.dynamic_limit_engine import DynamicLimitEngine


usage_history = [45, 52, 48, 61, 70, 45, 50]

addiction_engine = AddictionEngine()
limit_engine = DynamicLimitEngine(base_limit_minutes=120)

scores = addiction_engine.calculate_scores(usage_history)
current_score = addiction_engine.current_score(usage_history)
score_level = addiction_engine.score_level(current_score)

recommended_limit = limit_engine.recommend_limit(current_score)

friction = limit_engine.friction_action(
    usage_today=usage_history[-1],
    recommended_limit=recommended_limit
)

print("Usage History:", usage_history)
print("Addiction Scores:", scores)
print("Current Score:", current_score)
print("Score Level:", score_level)
print("Recommended Limit:", recommended_limit)
print("Friction Action:", friction)