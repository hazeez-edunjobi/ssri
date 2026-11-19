"""Release-shell label inventory join onto Stage 2.5 tiles."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from ssri_model.ml.constants import LABEL_NODATA
from ssri_model.release_shell.labels_inventory import (
    LabelInventory,
    LabelRecord,
    apply_labels_to_dataset,
    join_labels_to_grid,
)


def _sample(root: Path, *, x0: float = 1000.0, y0: float = 2000.0) -> Path:
    sample = root / "train" / "s1"
    sample.mkdir(parents=True)
    data = np.full((4, 4), LABEL_NODATA, dtype=np.int16)
    transform = from_origin(x0, y0 + 400, 100, 100)
    with rasterio.open(
        sample / "label.tif",
        "w",
        driver="GTiff",
        height=4,
        width=4,
        count=1,
        dtype="int16",
        crs="EPSG:32631",
        transform=transform,
        nodata=LABEL_NODATA,
    ) as ds:
        ds.write(data, 1)
    np.save(sample / "feature_stack.npy", np.zeros((13, 4, 4), dtype=np.float32))
    return sample


def test_join_labels_to_grid_snaps_within_half_cell() -> None:
    xs = [1000.0, 1100.0, 1200.0]
    ys = [2000.0, 2100.0, 2200.0]
    inventory = LabelInventory(
        crs="EPSG:32631",
        records=[LabelRecord(x=1105.0, y=2102.0, hazard="landslide", class_id=1)],
        counts_by_hazard={"landslide": 1},
    )
    on_grid, counts = join_labels_to_grid(
        inventory, xs, ys, x_spacing=100.0, y_spacing=100.0
    )
    assert counts["landslide"] == 1
    assert (1100.0, 2100.0) in on_grid or any(
        abs(k[0] - 1100.0) < 1e-6 and abs(k[1] - 2100.0) < 1e-6 for k in on_grid
    )


def test_apply_labels_writes_class_ids(tmp_path: Path) -> None:
    _sample(tmp_path, x0=1000.0, y0=2000.0)
    # Cell centres for from_origin(1000, 2400, 100, 100): x=1050,1150,... y=2350,2250,...
    inventory = LabelInventory(
        crs="EPSG:32631",
        records=[
            LabelRecord(x=1050.0, y=2350.0, hazard="subsidence", class_id=0),
            LabelRecord(x=1150.0, y=2250.0, hazard="landslide", class_id=1),
        ],
        counts_by_hazard={"subsidence": 1, "landslide": 1},
    )
    result = apply_labels_to_dataset(tmp_path, inventory)
    assert result["labels_joined"] >= 1
    with rasterio.open(tmp_path / "train" / "s1" / "label.tif") as ds:
        arr = ds.read(1)
    assert 0 in arr or 1 in arr
