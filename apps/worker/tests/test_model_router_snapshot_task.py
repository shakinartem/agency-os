from apps.worker.tasks.model_router_snapshot_tasks import refresh_model_router_snapshot


def test_model_router_snapshot_task_is_registered_name():
    assert refresh_model_router_snapshot.name == "content_factory.refresh_model_router_snapshot"
