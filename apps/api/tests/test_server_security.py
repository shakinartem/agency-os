import pytest
from pydantic import ValidationError

from app.access import ROLE_CAPABILITIES
from app.config import AppConfig


def test_project_roles_are_least_privilege():
    assert "content:publish" not in ROLE_CAPABILITIES["viewer"]
    assert "experiments:manage" not in ROLE_CAPABILITIES["reviewer"]
    assert "members:manage" in ROLE_CAPABILITIES["owner"]
    assert "performance:manage" in ROLE_CAPABILITIES["editor"]


def test_production_rejects_weak_defaults():
    with pytest.raises(ValidationError):
        AppConfig(
            _env_file=None,
            app_env="production",
            database_url="postgresql+asyncpg://u:p@db/x",
            session_cookie_secure=True,
            cors_origins=["https://factory.example.com"],
            allowed_hosts=["factory.example.com"],
        )


def test_production_accepts_explicit_safe_config():
    cfg = AppConfig(
        _env_file=None,
        app_env="production",
        secret_key="a" * 40,
        database_url="postgresql+asyncpg://u:p@db/x",
        session_cookie_secure=True,
        cors_origins=["https://factory.example.com"],
        allowed_hosts=["factory.example.com"],
        api_docs_enabled=False,
    )
    assert cfg.is_production


def test_manual_content_status_cannot_skip_review_workflow():
    from app.schemas.content import ContentItemCreate, ContentItemUpdate

    with pytest.raises(ValidationError):
        ContentItemCreate(project_id="00000000-0000-0000-0000-000000000001", title="x", status="ready")
    with pytest.raises(ValidationError):
        ContentItemUpdate(status="published")


def test_performance_metrics_reject_non_finite_and_extreme_values():
    from datetime import datetime, timezone
    from app.schemas.factory import PerformanceIngest

    base = {
        "event_id": "evt-1",
        "source": "autoposter",
        "content_id": "00000000-0000-0000-0000-000000000001",
        "external_publication_id": "pub-1",
        "captured_at": datetime.now(timezone.utc),
    }
    for value in (float("nan"), float("inf"), -1, 1e16):
        with pytest.raises(ValidationError):
            PerformanceIngest(**base, metrics={"views": value})
