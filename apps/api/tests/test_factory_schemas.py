import pytest
from pydantic import ValidationError

from app.schemas.factory import BatchCreate, PerformanceIngest, ReviewDecisionPayload


def test_batch_content_mix_is_bounded():
    value = BatchCreate(project_id="x", objective="Create a monthly content series", content_mix={"post": 8, "article": 2})
    assert value.content_mix == {"post": 8, "article": 2}
    with pytest.raises(ValidationError):
        BatchCreate(project_id="x", objective="Create a monthly content series", content_mix={"post": 101})


def test_review_reason_codes_are_controlled():
    value = ReviewDecisionPayload(reason_codes=["weak_hook", "weak_hook", "off_brand"])
    assert value.reason_codes == ["weak_hook", "off_brand"]
    with pytest.raises(ValidationError):
        ReviewDecisionPayload(reason_codes=["invented_reason"])


def test_performance_metrics_cannot_be_negative():
    PerformanceIngest(
        event_id="evt-1",
        content_id="11111111-1111-1111-1111-111111111111",
        external_publication_id="pub-1",
        captured_at="2026-08-17T18:00:00Z",
        metrics={"views": 100, "clicks": 2},
    )
    with pytest.raises(ValidationError):
        PerformanceIngest(
            event_id="evt-2",
            content_id="11111111-1111-1111-1111-111111111111",
            external_publication_id="pub-1",
            captured_at="2026-08-17T18:00:00Z",
            metrics={"views": -1},
        )
