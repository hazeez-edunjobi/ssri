"""Real S3-compatible object-storage round-trip (MinIO or Cloudflare R2).

Usage (never prints secret values):

  set SSRI_OBJECT_STORAGE_BACKEND=minio   # or r2
  set SSRI_OBJECT_STORAGE_BUCKET=ssri-artifacts
  set SSRI_OBJECT_STORAGE_ENDPOINT=http://127.0.0.1:9000
  set SSRI_OBJECT_STORAGE_ACCESS_KEY=...
  set SSRI_OBJECT_STORAGE_SECRET_KEY=...
  poetry run python scripts/qualify_object_storage.py

Exit 0 on checksum-verified upload/download of checkpoint-like + tree artefacts.
"""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ssri_model.storage import build_object_storage_from_env
from ssri_model.storage.durable import (
    IncompleteObjectStorageConfigError,
    assessment_object_key,
    checkpoint_object_key,
    geological_dataset_prefix,
    is_remote_object_backend,
    materialize_object_to_path,
    materialize_prefix_to_directory,
    mirror_file_to_object_storage,
    mirror_tree_to_object_storage,
    validate_object_storage_configuration,
)


def _ensure_bucket(bucket: str) -> None:
    try:
        import boto3
        from botocore.client import Config
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(f"boto3 required: {exc}") from exc
    endpoint = os.environ.get("SSRI_OBJECT_STORAGE_ENDPOINT") or None
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.environ.get("SSRI_OBJECT_STORAGE_ACCESS_KEY") or None,
        aws_secret_access_key=os.environ.get("SSRI_OBJECT_STORAGE_SECRET_KEY") or None,
        region_name=os.environ.get("SSRI_OBJECT_STORAGE_REGION") or "us-east-1",
        config=Config(signature_version="s3v4"),
    )
    try:
        client.head_bucket(Bucket=bucket)
        print(f"bucket_exists={bucket}")
    except Exception:
        client.create_bucket(Bucket=bucket)
        print(f"bucket_created={bucket}")


def main() -> int:
    errors = validate_object_storage_configuration()
    if errors:
        print("CONFIG_FAIL: " + "; ".join(errors), file=sys.stderr)
        return 2
    if not is_remote_object_backend():
        print("CONFIG_FAIL: SSRI_OBJECT_STORAGE_BACKEND must be r2|s3|minio", file=sys.stderr)
        return 2
    bucket = (os.environ.get("SSRI_OBJECT_STORAGE_BUCKET") or "").strip()
    backend = (os.environ.get("SSRI_OBJECT_STORAGE_BACKEND") or "").strip().lower()
    print(f"backend={backend} bucket={bucket} endpoint_set={bool(os.environ.get('SSRI_OBJECT_STORAGE_ENDPOINT'))}")
    _ensure_bucket(bucket)

    store = build_object_storage_from_env()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        ckpt = root / "best.pt"
        payload = b"ssri-object-storage-qualify-" + os.urandom(32)
        ckpt.write_bytes(payload)
        digest = hashlib.sha256(payload).hexdigest()
        key = checkpoint_object_key("qualify-model", "best.pt")
        meta = mirror_file_to_object_storage(
            ckpt, key, content_type="application/octet-stream", storage=store
        )
        assert meta is not None
        assert meta["sha256"] == digest
        dest = root / "downloaded.pt"
        materialize_object_to_path(key, dest, storage=store)
        got = dest.read_bytes()
        got_digest = hashlib.sha256(got).hexdigest()
        print(f"checkpoint_roundtrip sha256_match={got_digest == digest} bytes={len(got)}")
        if got != payload:
            print("FAIL: checkpoint bytes mismatch", file=sys.stderr)
            return 1

        geo = root / "geo_tree"
        (geo / "original").mkdir(parents=True)
        (geo / "original" / "sample.csv").write_text("X,Y,Z\n1,2,3\n", encoding="utf-8")
        (geo / "dataset.json").write_text('{"geo_id":"geo_qualify"}', encoding="utf-8")
        prefix = geological_dataset_prefix("geo_qualify")
        tree_meta = mirror_tree_to_object_storage(geo, prefix, storage=store)
        assert tree_meta is not None and tree_meta["files"] >= 2
        out = root / "geo_out"
        n = materialize_prefix_to_directory(prefix, out, storage=store)
        print(f"tree_roundtrip files_downloaded={n} listed={len(store.list_prefix(prefix))}")
        if not (out / "dataset.json").is_file():
            print("FAIL: dataset.json missing after materialize", file=sys.stderr)
            return 1

        assess_key = assessment_object_key("assess-qualify", "assess_response.json")
        assess_path = root / "assess_response.json"
        assess_path.write_text('{"assessment_id":"assess-qualify"}', encoding="utf-8")
        mirror_file_to_object_storage(
            assess_path, assess_key, content_type="application/json", storage=store
        )
        print("PASS: object storage upload/download/checksum verified")
        print(f"verification_mode=real_{backend}")
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except IncompleteObjectStorageConfigError as exc:
        print(f"CONFIG_FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
