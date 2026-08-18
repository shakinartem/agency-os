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


def test_performance_informed_plan_enforces_exploration_floor():
    rubric = "11111111-1111-1111-1111-111111111111"
    items = [
        {"content_type": "post", "topic": f"Topic {index}", "rubric_id": rubric, "learning_mode": "exploit"}
        for index in range(4)
    ]
    errors = validate_batch_plan(items, {"post": 4}, {rubric}, min_exploration_share=0.25)
    assert any("exploration floor" in error for error in errors)

    items[-1]["learning_mode"] = "explore"
    assert validate_batch_plan(items, {"post": 4}, {rubric}, min_exploration_share=0.25) == []


def test_exploration_policy_requires_explicit_learning_mode():
    items = [
        {"content_type": "post", "topic": "One", "rubric_id": None, "learning_mode": "explore"},
        {"content_type": "post", "topic": "Two", "rubric_id": None},
    ]
    errors = validate_batch_plan(items, {"post": 2}, set(), min_exploration_share=0.25)
    assert any("learning_mode" in error for error in errors)
