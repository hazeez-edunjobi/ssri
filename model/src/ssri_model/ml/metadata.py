"""Sample metadata schemas for SSRI datasets."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class SampleMetadata:
    """Metadata describing a single generated SSRI feature sample."""

    sample_id: str
    aoi: Mapping[str, Any]
    acquisition: Mapping[str, str]
    resolution_m: float
    crs: str
    sources: Mapping[str, str]
    package_version: str
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert metadata to a JSON-serializable dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> SampleMetadata:
        """Build metadata from a dictionary."""
        return cls(
            sample_id=str(payload["sample_id"]),
            aoi=dict(payload["aoi"]),
            acquisition=dict(payload["acquisition"]),
            resolution_m=float(payload["resolution_m"]),
            crs=str(payload["crs"]),
            sources=dict(payload["sources"]),
            package_version=str(payload["package_version"]),
            created_at=str(payload["created_at"]),
        )

    def save(self, path: Path | str) -> Path:
        """Persist metadata to a JSON file."""
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", encoding="utf-8") as handle:
            json.dump(self.to_dict(), handle, indent=2)
        return destination

    @classmethod
    def load(cls, path: Path | str) -> SampleMetadata:
        """Load metadata from a JSON file."""
        with Path(path).open(encoding="utf-8") as handle:
            payload = json.load(handle)
        return cls.from_dict(payload)
