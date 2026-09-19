import logging

from celery import Celery
from celery.signals import worker_init, worker_shutdown

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

celery_app = Celery(
    settings.worker_name,
    broker=settings.broker_url,
    backend=settings.result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


@worker_init.connect
def on_worker_init(**kwargs: object) -> None:
    """Log placeholder message when the worker process starts."""
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    logger.info("Starting %s", settings.worker_name)
    logger.info("Broker: %s", settings.broker_url)
    logger.info("Worker ready and waiting for tasks")


@worker_shutdown.connect
def on_worker_shutdown(**kwargs: object) -> None:
    """Log placeholder message when the worker process shuts down."""
    logger.info("Shutting down %s", settings.worker_name)
