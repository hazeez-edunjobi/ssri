"""Readiness must recover and report durable geophysics assets."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from ssri_model.api.routes.health import (
    _geophysics_required_for_readiness,
    _public_geophysics_status,
)
from ssri_model.storage.durable import (
    ensure_geophysics_assets_local,
    sha256_bytes,
)


def _write_tiny_geotiff(path: Path) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    transform = from_origin(2.5, 7.5, 1.0 / 30.0, 1.0 / 30.0)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=2,
        width=2,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=transform,
        nodata=-9999.0,
    ) as dst:
        dst.write(np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32), 1)
    return path.read_bytes()


def test_production_requires_geophysics(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SSRI_LIVE_ACQUISITION_ENABLED", raising=False)
    cfg = SimpleNamespace(
        service_config=SimpleNamespace(environment=SimpleNamespace(value="production"))
    )
    assert _geophysics_required_for_readiness(cfg) is True  # type: ignore[arg-type]


def test_public_geophysics_status_hides_paths() -> None:
    public = _public_geophysics_status(
        {
            "available": True,
            "materialized_count": 1,
            "processed_dir_configured": "/data/geophysics/processed",
            "assets": [
                {
                    "filename": "lagos_gravity_wgm2012_bouguer.tif",
                    "present": True,
                    "sha256_ok": True,
                    "valid_geotiff": True,
                    "materialized": False,
                    "bytes": 14113,
                    "detail": "ok",
                    "raster": {"bands": 1, "crs": "EPSG:4326"},
                }
            ],
            "detail": "ok",
        }
    )
    dumped = str(public)
    assert "/data/" not in dumped
    assert public["available"] is True
    assert public["assets"][0]["filename"] == "lagos_gravity_wgm2012_bouguer.tif"


def test_ensure_geophysics_idempotent_with_matching_local(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import ssri_model.storage.durable as durable

    monkeypatch.setenv("SSRI_OBJECT_STORAGE_BACKEND", "local")
    payload = _write_tiny_geotiff(tmp_path / "src.tif")
    digest = sha256_bytes(payload)
    filename = "lagos_gravity_wgm2012_bouguer.tif"
    dest_dir = tmp_path / "processed"
    dest_dir.mkdir(parents=True)
    (dest_dir / filename).write_bytes(payload)
    (dest_dir / "lagos_magnetic_emag2v3_uc4km.tif").write_bytes(payload)
    monkeypatch.setattr(
        durable,
        "REQUIRED_GEOPHYSICS_ASSETS",
        (
            {
                "filename": filename,
                "object_key": f"geophysics/processed/{filename}",
                "expected_sha256": digest,
                "expected_bytes": len(payload),
            },
            {
                "filename": "lagos_magnetic_emag2v3_uc4km.tif",
                "object_key": "geophysics/processed/lagos_magnetic_emag2v3_uc4km.tif",
                "expected_sha256": digest,
                "expected_bytes": len(payload),
            },
        ),
    )
    result = ensure_geophysics_assets_local(processed_dir=dest_dir)
    assert result["available"] is True
    assert result["materialized_count"] == 0
