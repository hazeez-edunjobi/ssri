"""Upload row/byte caps: no hard 250k row limit; streaming parse; 413 on byte overflow.

SYNTHETIC fixtures only — not production geology.
"""

from __future__ import annotations

import inspect
import io
import os
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ssri_model.api.app import create_app
from ssri_model.manual_training.csv_import import CsvFeatureOnly, convert_csv_dataset, iter_csv_rows
from ssri_model.manual_training.exceptions import ManualTrainingError
from ssri_model.manual_training.upload_limits import reject_if_upload_too_large, upload_max_bytes, upload_max_rows
from ssri_model.platform.store import MemoryPlatformStore
from tests.api_helpers import build_api_config


def _synthetic_xyz_csv(width: int, height: int) -> bytes:
    """Regular grid X,Y,Z — labelled SYNTHETIC by filename convention in callers."""
    buf = io.StringIO()
    buf.write("X,Y,Z\n")
    for y in range(height):
        for x in range(width):
            buf.write(f"{x * 100},{y * 100},{x + y}\n")
    return buf.getvalue().encode()


def test_upload_max_rows_default_unlimited(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SSRI_UPLOAD_MAX_ROWS", raising=False)
    assert upload_max_rows() is None


def test_upload_max_bytes_default_2gib(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SSRI_UPLOAD_MAX_BYTES", raising=False)
    assert upload_max_bytes() == 2 * 1024 * 1024 * 1024


def test_iter_csv_rows_streams_and_is_not_a_list() -> None:
    content = _synthetic_xyz_csv(4, 4)
    rows = iter_csv_rows("SYNTHETIC_grid.csv", content)
    assert not isinstance(rows, list)
    assert inspect.isgenerator(rows) or hasattr(rows, "__next__")
    first = next(rows)
    assert set(first) >= {"X", "Y", "Z"}
    # Remainder must still be iterable without materializing the whole file first.
    rest = list(rows)
    assert len(rest) == 15


def test_parser_does_not_return_full_row_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guard: streaming API must not silently reintroduce list materialization."""
    monkeypatch.delenv("SSRI_UPLOAD_MAX_ROWS", raising=False)
    content = _synthetic_xyz_csv(8, 8)
    produced = iter_csv_rows("SYNTHETIC.csv", content)
    assert type(produced).__name__ != "list"
    assert sum(1 for _ in produced) == 64


@pytest.mark.parametrize("n_rows", [250_001, 1_000_000])
def test_synthetic_large_row_counts_pass_size_check_and_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    n_rows: int,
) -> None:
    monkeypatch.delenv("SSRI_UPLOAD_MAX_ROWS", raising=False)
    # Factor n_rows into a regular grid (width x height).
    width = 1000 if n_rows >= 1_000_000 else 641
    height = (n_rows + width - 1) // width
    assert width * height >= n_rows
    content = _synthetic_xyz_csv(width, height)
    assert content.count(b"\n") - 1 == width * height

    with pytest.raises(CsvFeatureOnly) as caught:
        convert_csv_dataset(
            tmp_path / f"SYNTHETIC_{n_rows}",
            filename="SYNTHETIC_elevation.csv",
            content=content,
            crs="EPSG:32631",
            dataset_name="SYNTHETIC large grid",
        )
    analysis = caught.value.analysis
    assert analysis["rows"] == width * height
    assert analysis["status"] == "FEATURE_LAYER_ONLY"
    assert analysis["grid"]["width"] == width
    assert analysis["grid"]["height"] == height


def test_optional_row_cap_still_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SSRI_UPLOAD_MAX_ROWS", "10")
    content = _synthetic_xyz_csv(4, 4)  # 16 data rows
    with pytest.raises(ManualTrainingError, match="more than 10 data rows") as caught:
        list(iter_csv_rows("SYNTHETIC.csv", content))
    assert caught.value.code == "CSV_TOO_LARGE"


def test_byte_limit_rejects_with_readable_413(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SSRI_UPLOAD_MAX_BYTES", "64")
    with pytest.raises(ManualTrainingError) as caught:
        reject_if_upload_too_large(65)
    assert caught.value.code == "UPLOAD_TOO_LARGE"
    assert "too large" in caught.value.message.lower()

    app = create_app(build_api_config(tmp_path))
    app.state.platform_store = MemoryPlatformStore()
    app.state.platform_tokens = {
        "user-a": ("11111111-1111-4111-8111-111111111111", "a@example.com", "user")
    }
    client = TestClient(app)
    created = client.post(
        "/api/v1/platform/datasets",
        headers={"Authorization": "Bearer user-a"},
        json={"name": "SYNTHETIC oversize"},
    )
    dataset_id = created.json()["dataset"]["id"]
    # Tiny CSV still over the 64-byte cap once headers + a few rows exist.
    content = _synthetic_xyz_csv(4, 4)
    assert len(content) > 64
    response = client.post(
        f"/api/v1/platform/datasets/{dataset_id}/versions",
        headers={"Authorization": "Bearer user-a"},
        files={"file": ("SYNTHETIC.csv", content, "text/csv")},
        data={"crs": "EPSG:32631"},
    )
    assert response.status_code == 413, response.text
    body = response.json()
    assert body["error"]["code"] == "UPLOAD_TOO_LARGE"
    assert "too large" in body["error"]["message"].lower()


def test_classic_training_upload_returns_413_when_over_byte_cap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SSRI_UPLOAD_MAX_BYTES", "32")
    app = create_app(build_api_config(tmp_path))
    client = TestClient(app)
    created = client.post("/api/v1/training/datasets", json={"name": "SYNTHETIC"})
    dataset_id = created.json()["dataset"]["dataset_id"]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("manifest.json", "{}")
    payload = buffer.getvalue()
    assert len(payload) > 32
    response = client.post(
        f"/api/v1/training/datasets/{dataset_id}/upload",
        files={"file": ("SYNTHETIC.zip", payload, "application/zip")},
    )
    assert response.status_code == 413, response.text
    assert response.json()["error"]["code"] == "UPLOAD_TOO_LARGE"
