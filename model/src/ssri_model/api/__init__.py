"""SSRI FastAPI HTTP layer (Stage 3.1)."""

from ssri_model.api.app import app, create_app
from ssri_model.api.config import APIConfig

__all__ = ["APIConfig", "app", "create_app"]
