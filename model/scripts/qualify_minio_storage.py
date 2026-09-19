"""Qualify S3-compatible storage against a local MinIO instance."""

from __future__ import annotations

import os
import urllib.request


def main() -> int:
    os.environ.setdefault("SSRI_OBJECT_STORAGE_BACKEND", "s3")
    os.environ.setdefault("SSRI_OBJECT_STORAGE_ENDPOINT", "http://127.0.0.1:9000")
    os.environ.setdefault("SSRI_OBJECT_STORAGE_BUCKET", "ssri-artifacts")
    os.environ.setdefault("SSRI_OBJECT_STORAGE_ACCESS_KEY", "ssri_minio")
    os.environ.setdefault("SSRI_OBJECT_STORAGE_SECRET_KEY", "ssri_minio_secret")
    os.environ.setdefault("SSRI_OBJECT_STORAGE_REGION", "us-east-1")

    import boto3
    from botocore.client import Config

    client = boto3.client(
        "s3",
        endpoint_url=os.environ["SSRI_OBJECT_STORAGE_ENDPOINT"],
        aws_access_key_id=os.environ["SSRI_OBJECT_STORAGE_ACCESS_KEY"],
        aws_secret_access_key=os.environ["SSRI_OBJECT_STORAGE_SECRET_KEY"],
        region_name=os.environ["SSRI_OBJECT_STORAGE_REGION"],
        config=Config(signature_version="s3v4"),
    )
    bucket = os.environ["SSRI_OBJECT_STORAGE_BUCKET"]
    try:
        client.create_bucket(Bucket=bucket)
        print("BUCKET=created")
    except Exception as exc:
        print(f"BUCKET={type(exc).__name__}")

    from ssri_model.storage import build_object_storage_from_env

    store = build_object_storage_from_env()
    key = store.put_bytes(
        "qualify/test.bin",
        b"hello-ssri",
        content_type="application/octet-stream",
    )
    url = store.signed_url(key, expires_seconds=60)
    data = urllib.request.urlopen(url, timeout=10).read()
    if data != b"hello-ssri":
        print("MINIO_S3=FAIL integrity")
        return 1
    store.delete(key)
    print("MINIO_S3=OK")
    print(f"SIGNED_URL_SCHEME={url.split(':', 1)[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
