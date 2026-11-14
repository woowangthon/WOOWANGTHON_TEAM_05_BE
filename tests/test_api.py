import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.models import Profile
from app.planner import build_plan

PROFILE = {"nationality": "대한민국", "purpose": "working_holiday", "visa_status": "preparing", "city": "Sydney", "arrival_date": "2027-02-01", "workplace": "Sydney CBD", "company": "", "monthly_budget": 3200, "initial_budget": 6000, "housing_type": "any", "max_commute": 45, "insurance": None, "sort_by": "balanced"}


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("AI_SERVICE_URL", raising=False)
    monkeypatch.delenv("BACKEND_API_KEY", raising=False)


def test_budget_and_unknown_costs():
    result = build_plan(Profile(**PROFILE))
    ash = next(h for h in result["options"] if h["id"] == "cda-ashfield")
    assert (ash["rent"], ash["monthly"], ash["initial"]) == (996.67, 2243.34, 0)
    assert ash["monthly_missing"] == ["의료·보험료"]
    red = next(h for h in result["options"] if h["id"] == "cda-redfern")
    assert red["bond"] is None and "보증금" in red["initial_missing"]


def test_create_revise_empty_and_validation():
    with TestClient(app) as client:
        assert client.post("/api/plans", json=PROFILE).status_code == 200
        result = client.post("/api/plans/revise", json={"profile": PROFILE, "message": "더 저렴하게, 통근 60분"}).json()
        assert result["changes"] == {"sort_by": "cheapest", "max_commute": 60}
        assert result["options"][0]["id"] == "cda-redfern"
        assert client.post("/api/plans", json={**PROFILE, "monthly_budget": 10}).json()["options"] == []
        for patch in [{"monthly_budget": -1}, {"workplace": "Paris"}, {"arrival_date": "2027-02-30"}, {"monthly_budget": "3000"}]:
            assert client.post("/api/plans", json={**PROFILE, **patch}).status_code == 422
        assert client.post("/api/plans/revise", json={"profile": PROFILE, "message": "알아서"}).status_code == 422


def test_api_key(monkeypatch):
    monkeypatch.setenv("BACKEND_API_KEY", "test-key")
    with TestClient(app) as client:
        assert client.post("/api/plans", json=PROFILE).status_code == 401
        assert client.post("/api/plans", json=PROFILE, headers={"X-API-Key": "test-key"}).status_code == 200


def test_reject_untrusted_model_fields(monkeypatch):
    monkeypatch.setenv("AI_SERVICE_URL", "http://ai.test")
    async def fake_call(endpoint, body):
        return {"changes": {"city": "Paris"}}
    monkeypatch.setattr("app.main.call_ai", fake_call)
    with TestClient(app) as client:
        assert client.post("/api/plans/revise", json={"profile": PROFILE, "message": "바꿔"}).status_code == 422


def test_ai_outage_is_visible(monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setenv("AI_SERVICE_URL", "http://ai.test")
    async def fake_call(endpoint, body):
        raise HTTPException(503, "unavailable")
    monkeypatch.setattr("app.main.call_ai", fake_call)
    with TestClient(app) as client:
        result = client.post("/api/plans", json=PROFILE).json()
        assert result["mode"] == "rules" and "Gemma" in result["warnings"][-1]
        assert client.post("/api/plans/revise", json={"profile": PROFILE, "message": "바꿔"}).status_code == 503


def test_purpose_and_visa_checklist():
    assert "visa" not in {g["id"] for g in build_plan(Profile(**{**PROFILE, "purpose": "employment"}))["guides"]}
    held = build_plan(Profile(**{**PROFILE, "visa_status": "held"}))
    assert "재확인" in next(g["title"] for g in held["guides"] if g["id"] == "visa")
