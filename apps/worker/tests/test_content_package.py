"""Contract tests for Content Factory -> Autoposter handoff."""

import pytest
from pydantic import ValidationError

from apps.worker.tasks.content_package import validate_content_package


def valid_payload():
    return {
        "schema_version": "content-package/1.0",
        "content_id": "content-1",
        "project_id": "project-1",
        "status": "approved",
        "canonical": {
            "content_type": "post",
            "topic": "Intent intelligence",
            "goal": "education",
            "title": "Why intent beats raw lead volume",
            "body": "Canonical body",
            "hook": "Hook",
            "cta": "CTA",
        },
        "variants": [
            {
                "platform": "telegram",
                "title": None,
                "plain_text": "Telegram body",
                "cta": "CTA",
                "hashtags": ["#intent"],
                "blocks": [],
                "media": [
                    {
                        "asset_id": "asset-1",
                        "type": "image",
                        "url": "https://cdn.example.com/content/asset.png",
                        "mime_type": "image/png",
                        "width": 1024,
                        "height": 1024,
                    }
                ],
            }
        ],
        "sources": [
            {
                "id": "S1",
                "title": "Source",
                "url": "https://example.com/source",
                "score": 0.92,
            }
        ],
        "quality": {
            "overall": 0.94,
            "factuality": 0.98,
            "brand_voice": 0.91,
            "media": 0.93,
        },
    }


def test_valid_package_is_normalized():
    package = validate_content_package(valid_payload())
    assert package["schema_version"] == "content-package/1.0"
    assert package["variants"][0]["platform"] == "telegram"
    assert package["sources"][0]["url"] == "https://example.com/source"


def test_schema_version_is_strict():
    payload = valid_payload()
    payload["schema_version"] = "content-package/2.0"
    with pytest.raises(ValidationError):
        validate_content_package(payload)


def test_unknown_top_level_fields_are_rejected():
    payload = valid_payload()
    payload["surprise"] = "not part of the contract"
    with pytest.raises(ValidationError):
        validate_content_package(payload)


def test_variant_requires_plain_text():
    payload = valid_payload()
    del payload["variants"][0]["plain_text"]
    with pytest.raises(ValidationError):
        validate_content_package(payload)


def test_v11_requires_exact_lineage():
    payload = valid_payload()
    payload["schema_version"] = "content-package/1.1"
    with pytest.raises(ValidationError):
        validate_content_package(payload)

    payload["lineage"] = {
        "content_version": 3,
        "export_delivery_id": "11111111-1111-1111-1111-111111111111",
        "generation_run_id": "22222222-2222-2222-2222-222222222222",
        "prompt_version": "factory-v4",
        "prompt_hash": "a" * 64,
        "model": "gpt-test",
        "model_router": {"reason": "shadow_only"},
        "shadow_experiment_ids": [],
    }
    normalized = validate_content_package(payload)
    assert normalized["schema_version"] == "content-package/1.1"
    assert normalized["lineage"]["content_version"] == 3
    assert normalized["lineage"]["prompt_hash"] == "a" * 64
