"""FastAPI application factory for SSRI."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ssri_model.api.config import APIConfig
from ssri_model.api.dependencies import (
    AppState,
    BatchExecutor,
    InferenceExecutor,
    create_app_state,
)
from ssri_model.api.errors import register_exception_handlers
from ssri_model.api.routes import assess, auth_keys, batch, health, inference, jobs, layers


def _configure_cors(app: FastAPI, config: APIConfig) -> None:
    import os

    raw = os.getenv("SSRI_CORS_ORIGINS") or os.getenv("CORS_ORIGINS") or ""
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    if not origins:
        if config.service_config.environment.value == "production":
            # Fail closed: no CORS origins configured in production.
            return
        origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
    if "*" in origins and config.service_config.environment.value == "production":
        raise RuntimeError("Wildcard CORS origins are not allowed in production")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    )

def create_app(
    api_config: APIConfig | None = None,
    *,
    inference_runner: Any | None = None,
    batch_inference_runner: Any | None = None,
    inference_executor: InferenceExecutor | None = None,
    batch_executor: BatchExecutor | None = None,
    key_store: Any | None = None,
) -> FastAPI:
    """Create a configured SSRI FastAPI application."""
    config = api_config or APIConfig.from_env()
    if api_config is None:
        from ssri_model.api.production_gate import assert_production_safe

        assert_production_safe()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        state = getattr(app.state, "ssri", None)
        if isinstance(state, AppState) and state.infrastructure is not None:
            state.infrastructure.shutdown(wait=False)

    app = FastAPI(
        title="SSRI Model API",
        version=config.service_version,
        docs_url="/docs" if config.docs_enabled else None,
        redoc_url="/redoc" if config.docs_enabled else None,
        openapi_url="/openapi.json" if config.docs_enabled else None,
        lifespan=lifespan,
    )
    _configure_cors(app, config)
    app.state.ssri = create_app_state(
        config,
        inference_runner=inference_runner,
        batch_inference_runner=batch_inference_runner,
        inference_executor=inference_executor,
        batch_executor=batch_executor,
        key_store=key_store,
    )
    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(health.health_router(config.api_prefix))
    app.include_router(inference.router, prefix=config.api_prefix)
    app.include_router(batch.router, prefix=config.api_prefix)
    app.include_router(assess.router, prefix=config.api_prefix)
    app.include_router(layers.router, prefix=config.api_prefix)
    app.include_router(auth_keys.router, prefix=config.api_prefix)
    app.include_router(jobs.router, prefix=config.api_prefix)

    return app


app = create_app()
