"""Spatial CSV conversion into the Stage 2.5 training contract."""

from __future__ import annotations

import io
import zipfile

import numpy as np
import pytest
from fastapi.testclient import TestClient

from ssri_model.api.app import create_app
from ssri_model.ml.constants import CHANNEL_NAMES
from ssri_model.manual_training.validation import validate_training_dataset
from ssri_model.platform.store import MemoryPlatformStore
from tests.api_helpers import build_api_config

WIDTH = 16
HEIGHT = 8


def _grid_csv(*, channels: list[str], label: str | None, skip: tuple[int, int] | None = None, x_gap: int = 100) -> bytes:
    header = ["X", "Y", *channels]
    if label is not None:
        header.append("label")
    lines = [",".join(header)]
    for y_index in range(HEIGHT):
        for x_index in range(WIDTH):
            if skip == (x_index, y_index):
                continue
            gap = 250 if x_index == 3 else x_gap
            # Keep regular spacing unless x_gap is the irregular sentinel handled below.
            x_value = -115500 + x_index * x_gap
            if x_gap < 0 and x_index > 0:
                x_value = -115500 + (x_index - 1) * 100 + 250
            y_value = 777400 + y_index * 100
            values = [str(x_value), str(y_value)]
            for index, _name in enumerate(channels):
                values.append(str(index + 1))
            if label is not None:
                values.append(label)
            lines.append(",".join(values))
    return ("\n".join(lines) + "\n").encode()


def _client(tmp_path):
    app = create_app(build_api_config(tmp_path))
    app.state.platform_store = MemoryPlatformStore()
    app.state.platform_tokens = {"user-a": ("11111111-1111-4111-8111-111111111111", "a@example.com", "user")}
    return TestClient(app)


def _upload(client: TestClient, content: bytes, name: str, crs: str = "EPSG:32631"):
    created = client.post(
        "/api/v1/platform/datasets",
        headers={"Authorization": "Bearer user-a"},
        json={"name": "CSV set"},
    )
    return client.post(
        f"/api/v1/platform/datasets/{created.json()['dataset']['id']}/versions",
        headers={"Authorization": "Bearer user-a"},
        files={"file": (name, content, "text/csv")},
        data={"crs": crs},
    )


def test_xyz_reconstructs_regular_grid_and_channel_order(tmp_path) -> None:
    content = _grid_csv(channels=list(CHANNEL_NAMES), label="1")
    response = _upload(_client(tmp_path), content, "features.csv")
    assert response.status_code == 200, response.text
    version = response.json()["version"]
    assert version["validation_status"] == "passed"
    analysis = version["preview"]["csv_analysis"]
    assert analysis["grid"] == {"width": WIDTH, "height": HEIGHT}
    assert analysis["x_spacing"] == 100
    assert analysis["y_spacing"] == 100
    assert analysis["crs"] == "EPSG:32631"
    assert analysis["labels_detected"] is True
    root = version["preview"]["extracted_root"]
    preview = validate_training_dataset(root)
    assert preview.validation_status == "passed"
    sample = next((tmp_path / "outputs").rglob("feature_stack.npy")) if False else None
    array = np.load(list(__import__("pathlib").Path(root).rglob("feature_stack.npy"))[0])
    assert array.shape[0] == 13
    assert array[0, 0, 0] == 1
    assert array[12, 0, 0] == 13


def test_single_xyz_layer_is_not_trainable(tmp_path) -> None:
    lines = ["X,Y,Z"]
    for y in range(4):
        for x in range(4):
            lines.append(f"{-115500 + x * 100},{777400 + y * 100},{50 + x}")
    response = _upload(_client(tmp_path), ("\n".join(lines)).encode(), "elevation.csv")
    assert response.status_code == 200, response.text
    version = response.json()["version"]
    assert version["validation_status"] == "failed"
    assert "cannot be used as a supervised training dataset" in version["validation_errors"][0]
    assert version["preview"]["csv_analysis"]["status"] == "FEATURE_LAYER_ONLY"


def test_csv_requires_crs_and_rejects_bad_spatial_data(tmp_path) -> None:
    client = _client(tmp_path)
    created = client.post(
        "/api/v1/platform/datasets",
        headers={"Authorization": "Bearer user-a"},
        json={"name": "CSV set"},
    )
    dataset_id = created.json()["dataset"]["id"]
    content = _grid_csv(channels=list(CHANNEL_NAMES), label="1")
    missing_crs = client.post(
        f"/api/v1/platform/datasets/{dataset_id}/versions",
        headers={"Authorization": "Bearer user-a"},
        files={"file": ("features.csv", content, "text/csv")},
    )
    assert missing_crs.status_code == 400
    assert "CRS is required" in missing_crs.json()["error"]["message"]

    duplicate = "X,Y,elevation,label\n1,2,3,0\n1,2,4,0\n"
    # Pad into a message check via the importer directly for specific grid errors.
    from ssri_model.manual_training.csv_import import convert_csv_dataset
    from ssri_model.manual_training.exceptions import ManualTrainingError

    with pytest.raises(ManualTrainingError, match="Duplicate spatial coordinate"):
        convert_csv_dataset(tmp_path / "dup", filename="a.csv", content=duplicate.encode(), crs="EPSG:32631", dataset_name="d")

    irregular = _grid_csv(channels=["elevation"], label=None, x_gap=-1)
    with pytest.raises(ManualTrainingError, match="irregular"):
        convert_csv_dataset(tmp_path / "irr", filename="elevation.csv", content=irregular, crs="EPSG:32631", dataset_name="d")

    missing_cell = _grid_csv(channels=list(CHANNEL_NAMES), label="0", skip=(1, 1))
    with pytest.raises(ManualTrainingError, match="missing"):
        convert_csv_dataset(tmp_path / "gap", filename="features.csv", content=missing_cell, crs="EPSG:32631", dataset_name="d")

    bad_label = _grid_csv(channels=list(CHANNEL_NAMES), label="9")
    with pytest.raises(ManualTrainingError, match="invalid label|label 9"):
        convert_csv_dataset(tmp_path / "lab", filename="features.csv", content=bad_label, crs="EPSG:32631", dataset_name="d")


def test_nodata_labels_and_mismatched_layers(tmp_path) -> None:
    content = _grid_csv(channels=list(CHANNEL_NAMES), label="-1")
    # One real class so the dataset is not an empty-label warning-only case.
    text = content.decode().replace(",-1\n", ",0\n", 1)
    response = _upload(_client(tmp_path), text.encode(), "features.csv")
    assert response.status_code == 200, response.text
    assert response.json()["version"]["validation_status"] == "passed"

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("elevation.csv", "X,Y,Z\n0,0,1\n100,0,1\n0,100,1\n100,100,1\n")
        archive.writestr("slope.csv", "X,Y,Z\n0,0,1\n200,0,1\n0,100,1\n200,100,1\n")
    from ssri_model.manual_training.csv_import import convert_csv_dataset
    from ssri_model.manual_training.exceptions import ManualTrainingError

    with pytest.raises(ManualTrainingError, match="does not cover the same X/Y grid"):
        convert_csv_dataset(
            tmp_path / "mismatch",
            filename="layers.zip",
            content=buffer.getvalue(),
            crs="EPSG:32632",
            dataset_name="mismatch",
        )


def test_multi_layer_zip_aligns_on_coordinates(tmp_path) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for index, name in enumerate(CHANNEL_NAMES):
            rows = ["X,Y,Z"]
            for y in range(HEIGHT):
                for x in range(WIDTH):
                    rows.append(f"{-115500 + x * 100},{777400 + y * 100},{index + 1}")
            archive.writestr(f"{name}.csv", "\n".join(rows))
        labels = ["X,Y,Z"]
        for y in range(HEIGHT):
            for x in range(WIDTH):
                labels.append(f"{-115500 + x * 100},{777400 + y * 100},0")
        archive.writestr("labels.csv", "\n".join(labels))
    response = _upload(_client(tmp_path), buffer.getvalue(), "layers.zip")
    assert response.status_code == 200, response.text
    assert response.json()["version"]["validation_status"] == "passed"
