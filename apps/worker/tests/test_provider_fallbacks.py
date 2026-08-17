"""Safety tests: missing external providers must never produce fake success."""

import asyncio

from apps.worker.tasks import providers


def test_research_without_key_is_explicitly_skipped(monkeypatch):
    monkeypatch.setattr(providers, "TAVILY_API_KEY", None)
    result = asyncio.run(providers.research_web("test query"))
    assert result["status"] == "skipped"
    assert result["sources"] == []
    assert "not configured" in result["reason"]


def test_autoposter_without_url_is_explicitly_skipped(monkeypatch):
    monkeypatch.setattr(providers, "AUTOPOSTER_URL", None)
    result = asyncio.run(providers.send_to_autoposter({"schema_version": "content-package/1.0"}, "key-1"))
    assert result["status"] == "skipped"
    assert "not configured" in result["reason"]


def test_storage_without_credentials_is_explicitly_skipped(monkeypatch):
    monkeypatch.setattr(providers, "S3_ENDPOINT_URL", None)
    result = asyncio.run(providers.store_media(b"image", "image/png", "content-1"))
    assert result["status"] == "skipped"
    assert "not configured" in result["reason"]
