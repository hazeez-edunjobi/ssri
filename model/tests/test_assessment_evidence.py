"""Tests for durable assessment acquisition evidence."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from ssri_model.api.assessment_evidence import (
    EVIDENCE_FILENAME,
    TENSOR_FILENAME,
    build_acquisition_evidence,
    evidence_status_for_assessment,
    persist_acquisition_evidence,
    sample_query_pixel_vector,
)
from ssri_model.ml.constants import CHANNEL_COUNT, CHANNEL_NAMES, FEATURE_NODATA
from ssri_model.storage import LocalObjectStorage
from ssri_model.storage.durable import (
    ensure_assessment_acquisition_evidence_local,
    mirror_assessment_acquisition_evidence,
    sha256_file,
)


def _tensor() -> np.ndarray:
    rng = np.random.default_rng(0)
    data = rng.normal(size=(CHANNEL_COUNT, 8, 8)).astype(np.float32)
    data[:, 0, 0] = FEATURE_NODATA
    return data


def test_sample_query_pixel_vector_marks_nodata() -> None:
    tensor = _tensor()
    sample = sample_query_pixel_vector(
        tensor,
        channel_names=CHANNEL_NAMES,
        pixel_row=0,
        pixel_col=0,
    )
    assert sample["all_valid"] is False
    assert all(item["nodata"] for item in sample["validity"])
    assert all(v is None for v in sample["values"])


def test_build_and_persist_evidence_checksums(tmp_path: Path) -> None:
    tensor = _tensor()
    evidence = persist_acquisition_evidence(
        output_root=tmp_path,
        assessment_id="assess-testevidence01",
        request_id="req-1",
        tensor=tensor,
        channel_names=CHANNEL_NAMES,
        acquisition_meta={
            "bbox": [3.2, 7.2, 3.22, 7.24],
            "resolution_m": 30.0,
            "crs": "EPSG:32631",
            "transform": [30.0, 0.0, 1.0, 0.0, -30.0, 2.0],
            "sources": {
                "dem": "copernicus",
                "gravity_provider": "wgm2012_bouguer",
                "magnetic_provider": "emag2v3_uc4km",
            },
        },
        location_provenance={"latitude": 7.24, "longitude": 3.21},
        checkpoint_id="ssri-model-1c8de63cd3",
        checkpoint_sha256="d912027e" + "0" * 56,
        pixel_row=3,
        pixel_col=4,
    )
    assert evidence["channel_names"] == list(CHANNEL_NAMES)
    assert evidence["query_pixel"]["pixel_row"] == 3
    assert len(evidence["query_pixel"]["values"]) == CHANNEL_COUNT
    acq = tmp_path / "assessments" / "assess-testevidence01" / "acquisition"
    assert (acq / TENSOR_FILENAME).is_file()
    assert (acq / EVIDENCE_FILENAME).is_file()
    loaded = json.loads((acq / EVIDENCE_FILENAME).read_text(encoding="utf-8"))
    assert loaded["artifacts"][TENSOR_FILENAME]["sha256"] == sha256_file(
        acq / TENSOR_FILENAME
    )
    assert loaded["scientific_validation_status"] == "NOT_VALIDATED"


def test_evidence_r2_mirror_and_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SSRI_OBJECT_STORAGE_BACKEND", "r2")
    monkeypatch.setenv("SSRI_OBJECT_STORAGE_BUCKET", "ssri")
    monkeypatch.setenv(
        "SSRI_OBJECT_STORAGE_ENDPOINT", "https://example.r2.cloudflarestorage.com"
    )
    monkeypatch.setenv("SSRI_OBJECT_STORAGE_ACCESS_KEY", "ak")
    monkeypatch.setenv("SSRI_OBJECT_STORAGE_SECRET_KEY", "sk")

    store = LocalObjectStorage(root=tmp_path / "objects")
    output_root = tmp_path / "outputs"
    assessment_id = "assess-recoverable01"
    persist_acquisition_evidence(
        output_root=output_root,
        assessment_id=assessment_id,
        request_id="req",
        tensor=_tensor(),
        channel_names=CHANNEL_NAMES,
        acquisition_meta={"sources": {"dem": "copernicus"}, "crs": "EPSG:32631"},
        location_provenance={},
        checkpoint_id="model",
        checkpoint_sha256="abc",
        pixel_row=1,
        pixel_col=1,
    )
    acq = output_root / "assessments" / assessment_id / "acquisition"
    meta = mirror_assessment_acquisition_evidence(
        acq, assessment_id, storage=store
    )
    assert meta is not None
    assert meta["uploaded"] >= 1

    # Wipe local acquisition tree and rematerialize.
    for path in acq.glob("*"):
        path.unlink()
    assert not (acq / EVIDENCE_FILENAME).is_file()
    n = ensure_assessment_acquisition_evidence_local(
        acq, assessment_id, storage=store
    )
    assert n >= 1
    status = evidence_status_for_assessment(output_root, assessment_id)
    assert status["available"] is True
    assert status["historical_gap"] is False


def test_historical_gap_when_evidence_missing(tmp_path: Path) -> None:
    status = evidence_status_for_assessment(tmp_path, "assess-oldhistory01")
    assert status["available"] is False
    assert status["historical_gap"] is True


def test_build_evidence_serialization_shape() -> None:
    doc = build_acquisition_evidence(
        assessment_id="assess-x",
        request_id="r",
        tensor=_tensor(),
        channel_names=CHANNEL_NAMES,
        acquisition_meta={"sources": {"gravity_provider": "wgm2012_bouguer"}},
        location_provenance={"latitude": 1.0, "longitude": 2.0},
        checkpoint_id="ckpt",
        checkpoint_sha256="deadbeef",
        pixel_row=2,
        pixel_col=2,
    )
    assert doc["channel_count"] == CHANNEL_COUNT
    assert doc["channel_order_contract"] == list(CHANNEL_NAMES)
    assert doc["acquisition_provenance"]["sources"]["gravity_provider"] == (
        "wgm2012_bouguer"
    )
