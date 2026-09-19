from app.celery_app import celery_app
from app.config import WorkerSettings, get_settings


def test_settings_defaults() -> None:
    settings = WorkerSettings()

    assert settings.worker_name == "ssri-worker"
    assert settings.broker_url == "redis://localhost:6379/0"


def test_get_settings_returns_cached_instance() -> None:
    get_settings.cache_clear()
    settings = get_settings()

    assert settings is get_settings()


def test_celery_uses_redis_broker() -> None:
    assert celery_app.main == "ssri-worker"
    assert celery_app.conf.broker_url.startswith("redis://")


def test_no_custom_tasks_registered() -> None:
    custom_tasks = [
        name for name in celery_app.tasks if not name.startswith("celery.")
    ]

    assert custom_tasks == []
