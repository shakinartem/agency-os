from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from database.model_router_cache import empty_model_router_report, snapshot_is_fresh


def test_empty_router_report_is_default_only_and_ui_safe(monkeypatch):
    monkeypatch.setenv("LLM_MODEL_CANDIDATES", "default,candidate")
    monkeypatch.setenv("CONTENT_PROMPT_VERSION", "prompt-v1")
    report = empty_model_router_report("default")
    assert report["default_model"] == "default"
    assert report["evidence_prompt_version"] == "prompt-v1"
    assert report["stages"]["draft"]["routing_ready"] is False
    assert report["stages"]["draft"]["recommended_model"] == "default"
    assert len(report["stages"]["draft"]["candidates"]) == 2


def test_snapshot_freshness_checks_ttl_candidate_config_and_prompt_cohort(monkeypatch):
    monkeypatch.setenv("MODEL_ROUTER_SNAPSHOT_TTL_SECONDS", "300")
    monkeypatch.setenv("LLM_MODEL_CANDIDATES", "default,candidate")
    monkeypatch.setenv("CONTENT_PROMPT_VERSION", "prompt-v1")
    payload = {
        "configured_candidates": ["default", "candidate"],
        "evidence_prompt_version": "prompt-v1",
    }
    fresh = SimpleNamespace(status="ready", default_model="default", refreshed_at=datetime.now(timezone.utc), payload=payload)
    assert snapshot_is_fresh(fresh, "default") is True

    stale = SimpleNamespace(status="ready", default_model="default", refreshed_at=datetime.now(timezone.utc) - timedelta(minutes=10), payload=payload)
    assert snapshot_is_fresh(stale, "default") is False

    wrong_config = SimpleNamespace(
        status="ready",
        default_model="default",
        refreshed_at=datetime.now(timezone.utc),
        payload={"configured_candidates": ["default"], "evidence_prompt_version": "prompt-v1"},
    )
    assert snapshot_is_fresh(wrong_config, "default") is False

    monkeypatch.setenv("CONTENT_PROMPT_VERSION", "prompt-v2")
    assert snapshot_is_fresh(fresh, "default") is False
