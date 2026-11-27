"""Read-only verification of durable geophysics objects in object storage.

Usage (with production R2 env vars set; never prints secret values)::

    poetry run python -m ssri_model.scripts.verify_geophysics_r2

Does not upload, delete, or overwrite remote objects.
"""

from __future__ import annotations

import json
import sys

from ssri_model.storage.durable import (
    IncompleteObjectStorageConfigError,
    ensure_geophysics_assets_local,
    validate_object_storage_configuration,
    verify_remote_geophysics_objects,
)


def main() -> int:
    errors = validate_object_storage_configuration()
    if errors:
        print(json.dumps({"ok": False, "config_errors": errors}, indent=2))
        return 2
    try:
        remote = verify_remote_geophysics_objects()
    except IncompleteObjectStorageConfigError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2
    print(json.dumps({"remote": remote}, indent=2))
    if not remote.get("ok"):
        return 1
    local = ensure_geophysics_assets_local()
    # Never print absolute processed_dir in CI logs if undesired; keep basename-only assets.
    safe_local = {
        "available": local.get("available"),
        "materialized_count": local.get("materialized_count"),
        "detail": local.get("detail"),
        "assets": [
            {
                "filename": a.get("filename"),
                "present": a.get("present"),
                "sha256_ok": a.get("sha256_ok"),
                "valid_geotiff": a.get("valid_geotiff"),
                "materialized": a.get("materialized"),
                "bytes": a.get("bytes"),
                "raster": a.get("raster"),
            }
            for a in local.get("assets") or []
        ],
    }
    print(json.dumps({"local_materialize": safe_local}, indent=2))
    return 0 if safe_local.get("available") else 1


if __name__ == "__main__":
    sys.exit(main())
