"""Checkpoint identity and fixture guards for assessments."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from ssri_model.service.exceptions import InvalidServiceRequestError

# Known non-production / E2E fixture dataset names (manifest ``name`` field).
FIXTURE_DATASET_NAMES = frozenset({"e2e", "demo", "fixture", "test"})


def sha256_file(path: Path | str, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def dataset_manifest_fields(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    manifest = payload.get("dataset_manifest")
    if not isinstance(manifest, dict):
        return None, None
    name = manifest.get("name") or manifest.get("dataset_name")
    version = manifest.get("version")
    return (
        str(name) if name is not None else None,
        str(version) if version is not None else None,
    )


def is_fixture_dataset_name(name: str | None) -> bool:
    if name is None:
        return False
    return name.strip().lower() in FIXTURE_DATASET_NAMES


def allow_fixture_checkpoints() -> bool:
    return os.getenv("SSRI_ALLOW_FIXTURE_CHECKPOINTS", "").lower() in {
        "1",
        "true",
        "yes",
    }


def api_environment() -> str:
    return os.getenv("SSRI_API_ENVIRONMENT", "development").strip().lower()


def enforce_fixture_checkpoint_policy(dataset_name: str | None) -> bool:
    """Return True if this is a fixture checkpoint that is allowed to proceed.

    Raises when fixtures are used in non-development environments without an
    explicit allow flag.
    """
    if not is_fixture_dataset_name(dataset_name):
        return False
    env = api_environment()
    if env in {"production", "staging", "prod"} and not allow_fixture_checkpoints():
        raise InvalidServiceRequestError(
            f"Checkpoint dataset_manifest.name={dataset_name!r} is a known fixture. "
            "Refusing assessment in non-development environments. "
            "Train a real checkpoint, or set SSRI_ALLOW_FIXTURE_CHECKPOINTS=true "
            "only for explicit qualification runs."
        )
    return True
