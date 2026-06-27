import pytest

from app.services.addiction_engine import AddictionEngine
from app.services.dynamic_limit_engine import DynamicLimitEngine


def test_addiction_scores_are_valid():
    engine = AddictionEngine()
    usage_history = [45, 52, 48, 61, 70, 45, 50]

    scores = engine.calculate_scores(usage_history)

    assert len(scores) == len(usage_history)
    assert all(score >= 0 for score in scores)


def test_current_score_matches_last_score():
    engine = AddictionEngine()
    usage_history = [45, 52, 48, 61, 70, 45, 50]

    scores = engine.calculate_scores(usage_history)
    current = engine.current_score(usage_history)

    assert current == scores[-1]


def test_empty_history_returns_zero():
    engine = AddictionEngine()

    assert engine.current_score([]) == 0.0


def test_negative_usage_raises():
    engine = AddictionEngine()

    with pytest.raises(ValueError):
        engine.calculate_scores([30, -5, 40])


def test_score_level_bands():
    engine = AddictionEngine()

    assert engine.score_level(5) == "LOW"
    assert engine.score_level(15) == "MODERATE"
    assert engine.score_level(30) == "HIGH"
    assert engine.score_level(50) == "SEVERE"


def test_recommended_limit_decreases_with_score():
    limit_engine = DynamicLimitEngine(base_limit_minutes=120)

    limit_low = limit_engine.recommend_limit(5)
    limit_moderate = limit_engine.recommend_limit(20)
    limit_high = limit_engine.recommend_limit(35)
    limit_severe = limit_engine.recommend_limit(70)

    assert limit_low >= limit_moderate >= limit_high >= limit_severe


def test_recommended_limit_never_below_minimum():
    limit_engine = DynamicLimitEngine(
        base_limit_minutes=120,
        minimum_limit_minutes=20
    )

    assert limit_engine.recommend_limit(999) >= 20


def test_friction_levels():
    limit_engine = DynamicLimitEngine(base_limit_minutes=120)
    recommended_limit = 100

    assert limit_engine.friction_action(60, recommended_limit)["level"] == "NONE"
    assert limit_engine.friction_action(80, recommended_limit)["level"] == "SOFT_WARNING"
    assert limit_engine.friction_action(95, recommended_limit)["level"] == "WARNING"
    assert limit_engine.friction_action(110, recommended_limit)["level"] == "LIGHT_COOLDOWN"
    assert limit_engine.friction_action(125, recommended_limit)["level"] == "MEDIUM_COOLDOWN"
    assert limit_engine.friction_action(140, recommended_limit)["level"] == "STRONG_COOLDOWN"


def test_friction_zero_limit_raises():
    limit_engine = DynamicLimitEngine()

    with pytest.raises(ValueError):
        limit_engine.friction_action(usage_today=50, recommended_limit=0)