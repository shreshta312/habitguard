"""
test_dashboard_canonical.py

Tests verifying that the dashboard API endpoints return canonical user data schemas.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_dashboard_user_summary_endpoint():
    res = client.get("/dashboard/test_dash_user/summary")
    assert res.status_code == 200
    data = res.json()
    assert "user_id" in data
    assert "active_usage_minutes" in data
    assert "unplanned_overuse_minutes" in data
    assert "status" in data


def test_dashboard_user_history_endpoint():
    res = client.get("/dashboard/test_dash_user/history?days=7")
    assert res.status_code == 200
    data = res.json()
    assert data["user_id"] == "test_dash_user"
    assert isinstance(data["history"], list)


def test_dashboard_user_platforms_endpoint():
    res = client.get("/dashboard/test_dash_user/platforms")
    assert res.status_code == 200
    data = res.json()
    assert data["user_id"] == "test_dash_user"
    assert isinstance(data["platforms"], dict)


def test_dashboard_user_goal_endpoint():
    res = client.get("/dashboard/test_dash_user/goal")
    assert res.status_code == 200
    data = res.json()
    assert data["user_id"] == "test_dash_user"
    assert "selected_domains" in data


def test_research_endpoints():
    opt_res = client.get("/dashboard/research/test_dash_user/optimization")
    assert opt_res.status_code == 200
    assert "temptation_formula" in opt_res.json()

    param_res = client.get("/dashboard/research/test_dash_user/parameters")
    assert param_res.status_code == 200
    assert "parameters" in param_res.json()

    outcome_res = client.get("/dashboard/research/test_dash_user/outcomes")
    assert outcome_res.status_code == 200
    assert "evaluation" in outcome_res.json()


def test_debug_health_endpoint():
    res = client.get("/dashboard/debug/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
