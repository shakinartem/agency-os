"""Agency OS background worker entry point."""

import os

from celery import Celery

broker_url = os.getenv("REDIS_URL", "redis://localhost:6380/0")

app = Celery("agency_os_worker", broker=broker_url)
app.conf.broker_connection_retry_on_startup = True


@app.task
def dummy():
    return "Worker ready"
