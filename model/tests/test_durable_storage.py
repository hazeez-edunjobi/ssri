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
