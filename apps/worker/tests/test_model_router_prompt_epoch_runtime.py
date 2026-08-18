from apps.worker.tasks import model_router_prompt_epoch_runtime
from database.model_router_prompt import current_content_prompt_version


def test_prompt_epoch_runtime_is_loaded_and_configurable(monkeypatch):
    monkeypatch.setenv("CONTENT_PROMPT_VERSION", "prompt-test-v2")
    assert current_content_prompt_version() == "prompt-test-v2"
    assert model_router_prompt_epoch_runtime.prompt_epoch_stage is not None
