from apps.worker.tasks.batch_validation import validate_batch_plan


def test_batch_plan_requires_exact_mix_and_unique_topics():
    rubric = "11111111-1111-1111-1111-111111111111"
    good = [
        {"content_type": "post", "topic": "Buyer intent signals", "rubric_id": rubric},
        {"content_type": "post", "topic": "Readiness scoring", "rubric_id": rubric},
        {"content_type": "article", "topic": "From signal to opportunity", "rubric_id": None},
    ]
    assert validate_batch_plan(good, {"post": 2, "article": 1}, {rubric}) == []
    duplicate = [*good]
    duplicate[1] = {**duplicate[1], "topic": "Buyer intent signals"}
    assert "topics must be distinct" in validate_batch_plan(duplicate, {"post": 2, "article": 1}, {rubric})


def test_batch_plan_rejects_wrong_mix_and_unknown_rubric():
    items = [
        {"content_type": "post", "topic": "One", "rubric_id": "bad-id"},
        {"content_type": "post", "topic": "Two", "rubric_id": None},
    ]
    errors = validate_batch_plan(items, {"post": 1, "article": 1}, set())
    assert any("content_type post" in error for error in errors)
    assert any("content_type article" in error for error in errors)
    assert any("unknown rubric_id" in error for error in errors)
