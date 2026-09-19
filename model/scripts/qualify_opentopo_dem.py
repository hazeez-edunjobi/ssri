"""Qualification probe: OpenTopography DEM download for a tiny AOI."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def main() -> int:
    if not os.getenv("OPENTOPOGRAPHY_API_KEY"):
        print("OPENTOPO_DEM=FAIL missing_api_key")
        return 1
    try:
        from ssri_model.data.topography import DEMType, download_dem, load_dem

        # Small Lagos-area bbox (~0.02 deg)
        bbox = (3.37, 6.51, 3.39, 6.53)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dem.tif"
            download_dem(bbox, path, dem_type=DEMType.COPERNICUS)
            grid = load_dem(path)
            print("OPENTOPO_DEM=OK")
            print(f"DEM_BYTES={path.stat().st_size}")
            print(f"DEM_SHAPE={tuple(grid.data.shape)}")
        return 0
    except Exception as exc:
        print(f"OPENTOPO_DEM=FAIL type={type(exc).__name__}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
