"""Agency OS — Background task worker entry point."""

from celery import Celery

app = Celery("agency_os_worker", broker="redis://redis:6379/0")


@app.task
def dummy():
    return "Worker ready"
