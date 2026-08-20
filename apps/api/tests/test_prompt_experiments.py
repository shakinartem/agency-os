from types import SimpleNamespace
import uuid

from database.prompt_experiments import candidate_prompt_version, choose_arm_index, summarize_arm_observations


def obs(*, delta=0.04, winner="candidate", status="passed", candidate=0.9, control=0.86, latency=900, cost=0.002):
    return SimpleNamespace(quality_delta=delta, winner=winner, status=status, candidate_quality=candidate,
                           control_quality=control, candidate_latency_ms=latency, candidate_cost_usd=cost)


def test_prompt_experiment_summary_is_sample_gated():
    report = summarize_arm_observations([obs() for _ in range(4)], min_samples=5)
    assert report["decision"] == "collecting"
    assert report["valid_samples"] == 4


def test_small_nominal_win_is_not_promoted_without_confidence():
    rows = [obs() for _ in range(7)] + [obs(delta=0.01, winner="production") for _ in range(3)]
    report = summarize_arm_observations(rows, min_samples=10)
    assert report["candidate_win_rate"] == 0.7
    assert report["decision"] == "inconclusive"
    assert report["candidate_win_rate_ci_low"] < 0.5


def test_strong_large_effect_can_be_promising():
    rows = [obs(delta=0.06, winner="candidate") for _ in range(90)] + [obs(delta=0.025, winner="production") for _ in range(10)]
    report = summarize_arm_observations(rows, min_samples=20)
    assert report["decision"] == "promising"
    assert report["candidate_win_rate_ci_low"] > 0.5
    assert report["quality_delta_ci_low"] > 0


def test_prompt_experiment_arm_assignment_is_retry_stable():
    run_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    experiment_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    first = choose_arm_index(run_id, experiment_id, 3)
    assert first == choose_arm_index(run_id, experiment_id, 3)
    assert first in {0, 1, 2}
    version = candidate_prompt_version("factory-v3", experiment_id, "candidate-a")
    assert version.startswith("factory-v3+exp:22222222:candidate-a")
