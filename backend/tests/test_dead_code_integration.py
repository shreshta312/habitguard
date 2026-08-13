import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from app.main import app, get_daily_usage_history_from_rollups, rollups_repo, sessions_repo, intent_service
from app.services.behavior_feature_service import BehaviorFeatureService
from app.services.temptation_estimator import TemptationEstimator

client = TestClient(app)

def test_get_daily_usage_history_from_rollups_empty():
    user_id = "u_test_empty_history"
    history = get_daily_usage_history_from_rollups(user_id)
    assert history == []

def test_get_daily_usage_history_from_rollups_aggregated():
    user_id = "u_test_agg_history"
    # Insert rollups for multiple days and domains
    rollups_repo.upsert_rollup(user_id, "2026-07-29", "youtube.com", focused_minutes=25.0)
    rollups_repo.upsert_rollup(user_id, "2026-07-29", "reddit.com", focused_minutes=15.0)
    rollups_repo.upsert_rollup(user_id, "2026-07-30", "youtube.com", focused_minutes=50.0)
    
    history = get_daily_usage_history_from_rollups(user_id)
    assert len(history) == 2
    # 2026-07-29 should be 25 + 15 = 40
    # 2026-07-30 should be 50
    assert history[0] == 40.0
    assert history[1] == 50.0

def test_behavior_feature_service_habit_stock():
    bfs = BehaviorFeatureService()
    features_low = bfs.extract_features(
        focused_minutes=10.0,
        planned_minutes=30.0,
        purpose="neutral",
        habit_stock_score=5.0
    )
    features_high = bfs.extract_features(
        focused_minutes=10.0,
        planned_minutes=30.0,
        purpose="neutral",
        habit_stock_score=40.0
    )
    
    assert "habit_stock" in features_low
    assert "habit_stock" in features_high
    
    assert features_low["habit_stock"] == round(5.0 / 40.0, 4)
    assert features_high["habit_stock"] == 1.0

def test_temptation_estimator_habit_stock_blending():
    estimator = TemptationEstimator()
    
    features_no_habit = {
        "plan_overrun_ratio": 0.0,
        "reopen_frequency": 0.0,
        "longest_uninterrupted_usage": 0.0,
        "rapid_switching": 0.0,
        "historical_overrun_rate": 0.0,
        "context_signal": 0.0,
        "habit_stock": 0.0
    }
    features_with_habit = {
        "plan_overrun_ratio": 0.0,
        "reopen_frequency": 0.0,
        "longest_uninterrupted_usage": 0.0,
        "rapid_switching": 0.0,
        "historical_overrun_rate": 0.0,
        "context_signal": 0.0,
        "habit_stock": 1.0
    }
    
    res_no_habit = estimator.estimate(features_no_habit, purpose="neutral")
    res_with_habit = estimator.estimate(features_with_habit, purpose="neutral")
    
    assert res_with_habit["temptation_estimate"] > res_no_habit["temptation_estimate"]
    # The difference should reflect the 0.15 blending weight of habit_stock
    assert round(res_with_habit["temptation_estimate"] - res_no_habit["temptation_estimate"], 2) == 0.15

def test_batch_endpoint_dead_code_integration():
    uid = f"u_integration_{datetime.now().timestamp()}"
    
    # 1. Seed some historical rollups to simulate habit stock accumulation
    rollups_repo.upsert_rollup(uid, "2026-07-28", "youtube.com", focused_minutes=80.0)
    rollups_repo.upsert_rollup(uid, "2026-07-29", "youtube.com", focused_minutes=95.0)
    rollups_repo.upsert_rollup(uid, "2026-07-30", "youtube.com", focused_minutes=110.0)
    
    # 2. Start a session
    resp_start = client.post(
        "/sessions/start",
        json={"user_id": uid, "domain": "youtube.com", "purpose": "temptation", "intended_minutes": 20.0}
    ).json()
    
    session_id = resp_start["session_id"]
    
    # 3. Send activity batch ping
    ts = datetime.now(timezone.utc).isoformat()
    resp_batch = client.post(
        f"/sessions/{session_id}/activity/batch",
        json={
            "activities": [
                {"client_event_id": "evt1", "event_timestamp_utc": ts, "focused_duration_ms": 60000}
            ]
        }
    ).json()
    
    assert "addiction_score" in resp_batch
    assert "addiction_level" in resp_batch
    assert "recommended_daily_limit" in resp_batch
    assert "structural_timer_summary" in resp_batch
    
    assert resp_batch["addiction_score"] > 0
    assert resp_batch["addiction_level"] in ("LOW", "MODERATE", "HIGH", "SEVERE")
    assert resp_batch["recommended_daily_limit"] > 0
    assert resp_batch["structural_timer_summary"]["mode"] == "CALIBRATION" # less than 10 days of history

def test_diagnostics_endpoint():
    resp = client.get("/diagnostics").json()
    assert "models_loaded" in resp
    assert resp["models_loaded"].get("anomaly_detector") is True
    assert resp["models_loaded"].get("risk_classifier") is True
    assert resp["models_loaded"].get("usage_forecaster") is True
    assert resp["models_loaded"].get("user_segmentation") is True
