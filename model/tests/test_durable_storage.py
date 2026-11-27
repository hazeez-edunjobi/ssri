"""Durable object-storage helpers (local FS + mocked S3/R2)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ssri_model.storage import LocalObjectStorage
from ssri_model.storage.durable import (
    IncompleteObjectStorageConfigError,
    checkpoint_object_key,
    mirror_file_to_object_storage,
    resolve_checkpoint_path,
    validate_object_storage_configuration,
)


def test_validate_r2_incomplete() -> None:
    errors = validate_object_storage_configuration(
        {
            "SSRI_OBJECT_STORAGE_BACKEND": "r2",
            "SSRI_OBJECT_STORAGE_BUCKET": "bucket",
        }
    )
    assert any("ENDPOINT" in e for e in errors)


def test_checkpoint_object_key_stable() -> None:
    assert checkpoint_object_key("ssri-model-abc", "best.pt") == (
        "training/models/ssri-model-abc/best.pt"
    )


def test_mirror_skipped_for_local_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SSRI_OBJECT_STORAGE_BACKEND", "local")
    path = tmp_path / "best.pt"
    path.write_bytes(b"ckpt")
    assert (
        mirror_file_to_object_storage(
            path, checkpoint_object_key("m1"), content_type="application/octet-stream"
        )
        is None
    )


def test_mirror_and_resolve_with_local_store_as_standin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Use LocalObjectStorage while pretending backend is r2 for helper coverage."""
    monkeypatch.setenv("SSRI_OBJECT_STORAGE_BACKEND", "r2")
    monkeypatch.setenv("SSRI_OBJECT_STORAGE_BUCKET", "ssri")
    monkeypatch.setenv("SSRI_OBJECT_STORAGE_ENDPOINT", "https://example.r2.cloudflarestorage.com")
    monkeypatch.setenv("SSRI_OBJECT_STORAGE_ACCESS_KEY", "ak")
    monkeypatch.setenv("SSRI_OBJECT_STORAGE_SECRET_KEY", "sk")

    store = LocalObjectStorage(root=tmp_path / "objects")
    src = tmp_path / "best.pt"
    src.write_bytes(b"checkpoint-bytes")
    meta = mirror_file_to_object_storage(
        src,
        checkpoint_object_key("model-1"),
        content_type="application/octet-stream",
        storage=store,
    )
    assert meta is not None
    assert meta["object_key"].endswith("best.pt")
    assert store.exists(meta["object_key"])

    missing_local = tmp_path / "missing.pt"
    resolved = resolve_checkpoint_path(
        local_path=missing_local,
        object_key=meta["object_key"],
        cache_dir=tmp_path / "cache",
        storage=store,
    )
    assert resolved.is_file()
    assert resolved.read_bytes() == b"checkpoint-bytes"


def test_mirror_tree_and_materialize_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SSRI_OBJECT_STORAGE_BACKEND", "r2")
    monkeypatch.setenv("SSRI_OBJECT_STORAGE_BUCKET", "ssri")
    monkeypatch.setenv("SSRI_OBJECT_STORAGE_ENDPOINT", "https://example.r2.cloudflarestorage.com")
    monkeypatch.setenv("SSRI_OBJECT_STORAGE_ACCESS_KEY", "ak")
    monkeypatch.setenv("SSRI_OBJECT_STORAGE_SECRET_KEY", "sk")

    from ssri_model.storage.durable import (
        geological_dataset_prefix,
        materialize_prefix_to_directory,
        mirror_tree_to_object_storage,
    )

    store = LocalObjectStorage(root=tmp_path / "objects")
    src = tmp_path / "geo"
    (src / "working").mkdir(parents=True)
    (src / "dataset.json").write_text('{"ok":true}', encoding="utf-8")
    (src / "working" / "a.txt").write_text("hello", encoding="utf-8")
    prefix = geological_dataset_prefix("geo_test1")
    meta = mirror_tree_to_object_storage(src, prefix, storage=store)
    assert meta is not None
    assert meta["files"] == 2
    dest = tmp_path / "restored"
    n = materialize_prefix_to_directory(prefix, dest, storage=store)
    assert n == 2
    assert (dest / "dataset.json").read_text(encoding="utf-8") == '{"ok":true}'
    assert (dest / "working" / "a.txt").read_text(encoding="utf-8") == "hello"


def test_discover_remote_geological_dataset_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SSRI_OBJECT_STORAGE_BACKEND", "r2")
    monkeypatch.setenv("SSRI_OBJECT_STORAGE_BUCKET", "ssri")
    monkeypatch.setenv("SSRI_OBJECT_STORAGE_ENDPOINT", "https://example.r2.cloudflarestorage.com")
    monkeypatch.setenv("SSRI_OBJECT_STORAGE_ACCESS_KEY", "ak")
    monkeypatch.setenv("SSRI_OBJECT_STORAGE_SECRET_KEY", "sk")

    from ssri_model.storage.durable import (
        discover_remote_geological_dataset_ids,
        geological_dataset_prefix,
        mirror_tree_to_object_storage,
    )

    store = LocalObjectStorage(root=tmp_path / "objects")
    src = tmp_path / "geo_abc"
    src.mkdir()
    (src / "dataset.json").write_text('{"geo_id":"geo_abc"}', encoding="utf-8")
    mirror_tree_to_object_storage(src, geological_dataset_prefix("geo_abc"), storage=store)
    ids = discover_remote_geological_dataset_ids(storage=store)
    assert ids == ["geo_abc"]


def test_incomplete_config_raises_on_mirror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SSRI_OBJECT_STORAGE_BACKEND", "r2")
    monkeypatch.setenv("SSRI_OBJECT_STORAGE_BUCKET", "ssri")
    monkeypatch.delenv("SSRI_OBJECT_STORAGE_ENDPOINT", raising=False)
    path = tmp_path / "best.pt"
    path.write_bytes(b"x")
    with pytest.raises(IncompleteObjectStorageConfigError):
        mirror_file_to_object_storage(
            path, "training/models/m/best.pt", content_type="application/octet-stream"
        )


def test_ensure_geophysics_assets_materializes_from_object_storage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Render wipe recovery: missing local GeoTIFFs rematerialize from R2 keys."""
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin

    from ssri_model.storage.durable import (
        REQUIRED_GEOPHYSICS_ASSETS,
        ensure_geophysics_assets_local,
        sha256_bytes,
        verify_remote_geophysics_objects,
    )

    monkeypatch.setenv("SSRI_OBJECT_STORAGE_BACKEND", "r2")
    monkeypatch.setenv("SSRI_OBJECT_STORAGE_BUCKET", "ssri")
    monkeypatch.setenv(
        "SSRI_OBJECT_STORAGE_ENDPOINT", "https://example.r2.cloudflarestorage.com"
    )
    monkeypatch.setenv("SSRI_OBJECT_STORAGE_ACCESS_KEY", "ak")
    monkeypatch.setenv("SSRI_OBJECT_STORAGE_SECRET_KEY", "sk")

    store = LocalObjectStorage(root=tmp_path / "objects")
    processed = tmp_path / "geophysics" / "processed"
    # Build tiny valid GeoTIFFs and place under the expected object keys with
    # matching digests by patching REQUIRED specs for this test.
    payloads: dict[str, bytes] = {}
    patched_assets = []
    for spec in REQUIRED_GEOPHYSICS_ASSETS:
        filename = str(spec["filename"])
        path = tmp_path / "src" / filename
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
        payload = path.read_bytes()
        digest = sha256_bytes(payload)
        key = str(spec["object_key"])
        store.put_bytes(key, payload, content_type="image/tiff")
        payloads[key] = payload
        patched_assets.append(
            {
                "filename": filename,
                "object_key": key,
                "expected_sha256": digest,
                "expected_bytes": len(payload),
            }
        )

    import ssri_model.storage.durable as durable

    monkeypatch.setattr(durable, "REQUIRED_GEOPHYSICS_ASSETS", tuple(patched_assets))

    remote = verify_remote_geophysics_objects(storage=store)
    assert remote["ok"] is True
    assert all(a["sha256_ok"] for a in remote["assets"])

    # Simulate empty Render disk.
    assert not processed.exists() or not any(processed.glob("*.tif"))
    result = ensure_geophysics_assets_local(storage=store, processed_dir=processed)
    assert result["available"] is True
    assert result["materialized_count"] == 2
    for spec in patched_assets:
        dest = processed / str(spec["filename"])
        assert dest.is_file()
        assert sha256_bytes(dest.read_bytes()) == spec["expected_sha256"]

    # Idempotent second pass must not re-download.
    again = ensure_geophysics_assets_local(storage=store, processed_dir=processed)
    assert again["available"] is True
    assert again["materialized_count"] == 0
