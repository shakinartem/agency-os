from apps.worker.tasks.prompt_experiment_runtime import _candidate_inputs, _compact_assignment


def test_candidate_prompt_delta_is_candidate_only():
    assignment = {"system_append": "Be concise", "prompt_append": "Use one CTA"}
    system, prompt = _candidate_inputs("SYSTEM", "PROMPT", assignment)
    assert system.startswith("SYSTEM") and "Be concise" in system
    assert prompt.startswith("PROMPT") and "Use one CTA" in prompt


def test_compact_assignment_does_not_leak_prompt_delta():
    assignment = {
        "experiment_id": "11111111-1111-1111-1111-111111111111",
        "arm_id": "22222222-2222-2222-2222-222222222222",
        "arm_key": "candidate-a",
        "system_append": "secret candidate delta",
        "prompt_append": "another secret delta",
    }
    compact = _compact_assignment(assignment)
    assert "system_append" not in compact
    assert "prompt_append" not in compact
    assert compact["evidence_scope"] == "prompt_experiment"
