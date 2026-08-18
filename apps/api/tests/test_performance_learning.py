from database.performance_learning import derive_learning_context


def record(rubric: str, *, views: int = 100, clicks: int = 0, leads: int = 0, conversions: int = 0, content_type: str = "post", platform: str = "telegram"):
    return {
        "rubric": rubric,
        "content_type": content_type,
        "platform": platform,
        "metrics": {"views": views, "clicks": clicks, "leads": leads, "conversions": conversions},
    }


def test_learning_refuses_to_optimize_tiny_samples():
    result = derive_learning_context([record("Lucky", clicks=50)])
    assert result["status"] == "insufficient_data"
    assert result["by_rubric"][0]["action"] == "explore"
    assert result["by_rubric"][0]["confidence"] == "low"


def test_learning_scales_only_after_sample_gate_and_preserves_exploration():
    rows = []
    for _ in range(5):
        rows.append(record("Strong", clicks=20))
        rows.append(record("Weak", clicks=2))
    result = derive_learning_context(rows)
    assert result["status"] == "learning"
    assert result["primary_metric"] == "ctr"
    strong = next(row for row in result["by_rubric"] if row["name"] == "Strong")
    weak = next(row for row in result["by_rubric"] if row["name"] == "Weak")
    assert strong["action"] == "scale_cautiously"
    assert weak["action"] == "reduce_and_retest"
    assert result["exploration_share"] >= 0.25
    assert result["recommendations"]["guidance"]


def test_learning_uses_business_outcomes_before_clicks():
    rows = []
    for _ in range(5):
        rows.append(record("Buyer intent", clicks=10, leads=3, conversions=1))
    result = derive_learning_context(rows)
    assert result["primary_metric"] == "conversions_per_1000_views"
    assert result["baseline"] == 10.0
