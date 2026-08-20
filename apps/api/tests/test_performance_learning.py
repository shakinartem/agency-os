from database.performance_learning import derive_learning_context


def record(
    rubric: str,
    *,
    views: int = 100,
    clicks: int = 0,
    leads: int = 0,
    conversions: int = 0,
    content_type: str = "post",
    platform: str = "telegram",
    account: str = "a",
):
    return {
        "rubric": rubric,
        "content_type": content_type,
        "platform": platform,
        "account_id": account,
        "metrics": {
            "views": views,
            "clicks": clicks,
            "leads": leads,
            "conversions": conversions,
        },
    }


def test_learning_refuses_to_optimize_tiny_samples():
    result = derive_learning_context(
        [record("Lucky", clicks=50)],
        primary_metric="ctr",
        min_action_sample=5,
    )
    assert result["status"] == "insufficient_data"
    assert result["by_rubric"][0]["action"] == "explore"
    assert result["by_rubric"][0]["confidence"] == "low"


def test_learning_scales_only_after_sample_gate_and_preserves_exploration():
    rows = []
    for _ in range(5):
        rows.append(record("Strong", clicks=20))
        rows.append(record("Weak", clicks=2))
    result = derive_learning_context(rows, primary_metric="ctr", min_action_sample=5)
    assert result["status"] == "learning"
    assert result["primary_metric"] == "ctr"
    strong = next(row for row in result["by_rubric"] if row["name"] == "Strong")
    weak = next(row for row in result["by_rubric"] if row["name"] == "Weak")
    assert strong["action"] == "scale_cautiously"
    assert weak["action"] == "reduce_and_retest"
    assert result["exploration_share"] >= 0.25
    assert result["recommendations"]["guidance"]


def test_business_metric_is_explicit_and_stable():
    rows = [record("Buyer intent", clicks=10, leads=3, conversions=1) for _ in range(5)]
    views = derive_learning_context(
        rows,
        primary_metric="views_per_publication",
        min_action_sample=5,
    )
    conversions = derive_learning_context(
        rows,
        primary_metric="conversions_per_1000_views",
        min_action_sample=5,
    )
    assert views["primary_metric"] == "views_per_publication"
    assert conversions["primary_metric"] == "conversions_per_1000_views"
    assert conversions["baseline"] == 10.0


def test_distribution_dimensions_are_context_only():
    rows = [record("Same rubric", clicks=20, platform="telegram", account="big") for _ in range(5)]
    rows += [record("Same rubric", clicks=1, platform="instagram", account="small") for _ in range(5)]
    result = derive_learning_context(rows, primary_metric="ctr", min_action_sample=5)
    assert all(row["action"] == "context_only" for row in result["by_platform"])
    assert all(row["action"] == "context_only" for row in result["by_account"])


def test_untrusted_legacy_publications_are_reported_but_not_counted():
    rows = [record("Trusted", clicks=10) for _ in range(5)]
    result = derive_learning_context(
        rows,
        primary_metric="ctr",
        min_action_sample=5,
        excluded_untrusted_publications=7,
    )
    assert result["trusted_publications"] == 5
    assert result["excluded_untrusted_publications"] == 7
    assert result["lineage_policy"] == "immutable_delivery_required"
    assert any("excluded from allocation learning" in item for item in result["recommendations"]["guidance"])
