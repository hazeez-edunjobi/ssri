"""SSRI distributed worker package."""

from ssri_model.worker.celery_app import celery_app, get_celery_app

__all__ = ["celery_app", "get_celery_app"]
