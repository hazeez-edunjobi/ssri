"""Extended object storage tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ssri_model.storage import LocalObjectStorage, S3CompatibleObjectStorage, build_object_storage_from_env


def test_local_object_storage_roundtrip(tmp_path: Path) -> None:
    store = LocalObjectStorage(root=tmp_path / "objects")
    key = store.put_bytes(
        "assessments/a1/prediction.tif",
        b"tiff-bytes",
        content_type="image/tiff",
    )
    assert (tmp_path / "objects" / key).read_bytes() == b"tiff-bytes"
    url = store.signed_url(key, expires_seconds=60)
    assert key in url
    store.delete(key)
    assert not (tmp_path / "objects" / key).exists()


def test_local_rejects_path_traversal(tmp_path: Path) -> None:
    store = LocalObjectStorage(root=tmp_path / "objects")
    with pytest.raises(ValueError):
        store.put_bytes("../etc/passwd", b"x", content_type="text/plain")


def test_build_local_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SSRI_OBJECT_STORAGE_BACKEND", "local")
    monkeypatch.setenv("SSRI_OBJECT_STORAGE_ROOT", str(tmp_path / "objs"))
    store = build_object_storage_from_env()
    assert isinstance(store, LocalObjectStorage)


def test_s3_signed_url_uses_presign(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = MagicMock()
    fake_client.generate_presigned_url.return_value = "https://example.test/signed"
    fake_client.put_object.return_value = {}

    class FakeSession:
        def client(self, *_args, **_kwargs):
            return fake_client

    monkeypatch.setattr(
        "boto3.session.Session",
        lambda **_kwargs: FakeSession(),
    )
    store = S3CompatibleObjectStorage(bucket="ssri-artifacts")
    key = store.put_bytes("a/b.tif", b"data", content_type="image/tiff")
    assert key == "a/b.tif"
    url = store.signed_url(key, expires_seconds=120)
    assert url == "https://example.test/signed"
    fake_client.generate_presigned_url.assert_called_once()
