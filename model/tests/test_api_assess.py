"""Assessment API tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from ssri_model.api.app import create_app
from tests.api_helpers import build_api_config


def test_assess_requires_features_or_reports_aoi_gap(tmp_path) -> None:
    client = TestClient(create_app(build_api_config(tmp_path)))
    response = client.post(
        "/api/v1/assess",
        json={"point": {"latitude": 6.52, "longitude": 3.38}},
    )
    assert response.status_code in {400, 422}
    detail = str(response.json()).lower()
    assert "feature" in detail or "acquisition" in detail or "invalid" in detail


def test_assess_route_registered(tmp_path) -> None:
    app = create_app(build_api_config(tmp_path))
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/api/v1/assess" in paths
