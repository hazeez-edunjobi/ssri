import asyncio

from app.main import app
from app.routers.health import health_check


def test_health_returns_ok() -> None:
    response = asyncio.run(health_check())

    assert response.status == "ok"


def test_only_health_endpoint_exists() -> None:
    """Verify no other application routes are registered."""
    application_routes = {
        (route.path, frozenset(route.methods))
        for route in app.routes
        if hasattr(route, "methods")
        and route.path not in ("/openapi.json", "/docs", "/redoc")
        and not route.path.startswith("/docs")
    }

    assert application_routes == {("/health", frozenset({"GET"}))}
