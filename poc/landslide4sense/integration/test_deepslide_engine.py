"""Isolated regression tests for DeepSlide engine (not SSRI production suite)."""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = ROOT / "weights" / "mobilenetv2.pth"
HF_SHA256 = "a743e627dd68a1409ddda4ad43b70b53ee92c0d504d16c890e128ba04dc9ab4f"

from integration.deepslide_engine import (  # noqa: E402
    BAND_NAMES,
    EXPECTED_CHANNELS,
    IMG_MEAN,
    PREPROCESS_VERSION,
    DeepSlideEngine,
    package_raw_stack,
    write_georef_prediction,
)


@pytest.fixture(scope="module")
def engine() -> DeepSlideEngine:
    if not WEIGHTS.exists():
        pytest.skip("checkpoint missing")
    return DeepSlideEngine(WEIGHTS, threshold=0.5, device="cpu")


def test_checkpoint_sha256_matches_hf():
    h = hashlib.sha256(WEIGHTS.read_bytes()).hexdigest()
    assert h == HF_SHA256


def test_band_order_and_mean_vector():
    assert len(BAND_NAMES) == 14
    assert BAND_NAMES[0] == "B01"
    assert BAND_NAMES[11] == "B12"
    assert BAND_NAMES[12] == "slope_deg"
    assert BAND_NAMES[13] == "dem_m"
    assert IMG_MEAN.shape == (14,)
    assert IMG_MEAN[9] == pytest.approx(9.04787384)


def test_package_raw_rejects_wrong_shape():
    with pytest.raises(ValueError):
        package_raw_stack(np.zeros((13, 8, 8), dtype=np.float32))


def test_package_raw_scaling():
    raw = np.ones((14, 4, 4), dtype=np.float64)
    raw[0] = 1111.81236406
    pkg = package_raw_stack(raw)
    assert pkg.shape == (14, 4, 4)
    assert pkg.dtype == np.float32
    assert float(pkg[0].mean()) == pytest.approx(1.0, rel=1e-5)


def test_predict_packaged_l4s_chip(engine: DeepSlideEngine):
    import h5py

    chip = ROOT / "data" / "validation" / "images" / "image_10.h5"
    if not chip.exists():
        chip = ROOT / "data" / "images" / "image_1.h5"
    with h5py.File(chip, "r") as f:
        arr = np.array(f["img"], dtype=np.float32)
    if arr.shape[-1] == 14:
        arr = np.transpose(arr, (2, 0, 1))
    out = engine.predict_packaged(arr)
    assert out["score"].shape == (128, 128)
    assert out["mask"].dtype == np.uint8
    assert out["threshold"] == 0.5
    assert out["preprocess_version"] == PREPROCESS_VERSION
    assert "uncalibrated" in out["semantics"]
    assert out["checkpoint_sha256"] == HF_SHA256
    assert out["score_max"] > 0.5  # competition chip should fire


def test_predict_raw_optical_dn_required(engine: DeepSlideEngine):
    # Reflectance-scale (0-1) optical after packaging should stay near-empty vs DN-scale
    rng = np.random.default_rng(0)
    raw_dn = rng.uniform(100, 2000, size=(14, 64, 64))
    raw_dn[12] = rng.uniform(5, 40, size=(64, 64))  # slope
    raw_dn[13] = rng.uniform(100, 1500, size=(64, 64))  # dem
    out_dn = engine.predict_raw(raw_dn)

    raw_ref = raw_dn.copy()
    raw_ref[:12] = raw_ref[:12] / 10000.0
    out_ref = engine.predict_raw(raw_ref)
    assert out_dn["score_max"] >= out_ref["score_max"]


def test_invalid_input_raises(engine: DeepSlideEngine):
    with pytest.raises(ValueError):
        engine.predict_packaged(np.zeros((3, 32, 32), dtype=np.float32))


def test_geotiff_preserves_crs(tmp_path: Path, engine: DeepSlideEngine):
    rasterio = pytest.importorskip("rasterio")
    from rasterio.transform import from_origin

    packaged = np.zeros((14, 32, 32), dtype=np.float32)
    # inject L4S-like packaged noise so model can run
    packaged[:] = 0.5
    out = engine.predict_packaged(packaged)
    transform = from_origin(500000.0, 4800000.0, 10.0, 10.0)
    crs = "EPSG:32632"
    path = tmp_path / "out.tif"
    write_georef_prediction(path, out["mask"], out["score"], crs=crs, transform=transform)
    with rasterio.open(path) as src:
        assert str(src.crs) == crs
        assert src.count == 2
        assert src.transform == transform


def test_contract_excludes_subsidence_sinkhole(engine: DeepSlideEngine):
    assert engine.contract.hazards_supported == ("landslide",)
    assert "subsidence" in engine.contract.not_supported
    assert "sinkhole" in engine.contract.not_supported
    assert EXPECTED_CHANNELS == 14
