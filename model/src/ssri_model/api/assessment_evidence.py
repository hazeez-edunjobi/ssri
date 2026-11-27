"""Durable live-assessment acquisition evidence (tensor + compact audit JSON).

Evidence is written under ``assessments/{id}/acquisition/`` and mirrored to the
existing object-storage backend. Historical assessments created before this
module may lack evidence; callers must distinguish missing-historical from
available-future artefacts without fabricating channel values.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from ssri_model.ml.constants import CHANNEL_COUNT, CHANNEL_NAMES, FEATURE_NODATA

logger = logging.getLogger(__name__)

EVIDENCE_FILENAME = "acquisition_evidence.json"
TENSOR_FILENAME = "feature_stack.npy"
QUERY_VECTOR_FILENAME = "query_pixel_vector.json"


def assessment_evidence_object_key(assessment_id: str, filename: str) -> str:
    safe_id = assessment_id.replace("\\", "/").strip("/")
    name = Path(filename).name
    if ".." in safe_id.split("/") or not name or ".." in name:
        raise ValueError("unsafe assessment evidence object key")
    return f"assessments/{safe_id}/acquisition/{name}"


def acquisition_dir(output_root: Path, assessment_id: str) -> Path:
    return Path(output_root) / "assessments" / assessment_id / "acquisition"


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        tmp_path.replace(path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def _atomic_write_text(path: Path, text: str) -> None:
    _atomic_write_bytes(path, text.encode("utf-8"))


def _sha256_bytes(payload: bytes) -> str:
    from ssri_model.storage.durable import sha256_bytes

    return sha256_bytes(payload)


def _sha256_file(path: Path) -> str:
    from ssri_model.storage.durable import sha256_file

    return sha256_file(path)


def sample_query_pixel_vector(
    tensor: np.ndarray,
    *,
    channel_names: Sequence[str],
    pixel_row: int,
    pixel_col: int,
    nodata: float = FEATURE_NODATA,
) -> dict[str, Any]:
    """Sample the 13-channel vector at a query pixel with validity flags."""
    array = np.asarray(tensor)
    if array.ndim == 4:
        array = array[0]
    if array.ndim != 3:
        raise ValueError(f"tensor must be (C,H,W) or (B,C,H,W); got {array.shape}")
    channels, height, width = (int(array.shape[0]), int(array.shape[1]), int(array.shape[2]))
    if channels != len(channel_names):
        raise ValueError(
            f"channel_names length {len(channel_names)} != tensor channels {channels}"
        )
    if not (0 <= pixel_row < height and 0 <= pixel_col < width):
        raise ValueError(
            f"query pixel ({pixel_row},{pixel_col}) outside grid {height}x{width}"
        )
    values: list[float | None] = []
    validity: list[dict[str, Any]] = []
    for index, name in enumerate(channel_names):
        raw = float(array[index, pixel_row, pixel_col])
        is_finite = bool(np.isfinite(raw))
        is_nodata = bool(is_finite and abs(raw - float(nodata)) < 1e-3)
        ok = bool(is_finite and not is_nodata)
        values.append(raw if ok else None)
        validity.append(
            {
                "channel": name,
                "index": index,
                "finite": is_finite,
                "nodata": is_nodata,
                "valid": ok,
                "raw": raw if is_finite else None,
            }
        )
    return {
        "pixel_row": int(pixel_row),
        "pixel_col": int(pixel_col),
        "channel_names": list(channel_names),
        "values": values,
        "validity": validity,
        "nodata_sentinel": float(nodata),
        "all_valid": all(item["valid"] for item in validity),
    }


def build_acquisition_evidence(
    *,
    assessment_id: str,
    request_id: str | None,
    tensor: np.ndarray,
    channel_names: Sequence[str] | None,
    acquisition_meta: Mapping[str, Any] | None,
    location_provenance: Mapping[str, Any] | None,
    checkpoint_id: str | None,
    checkpoint_sha256: str | None,
    pixel_row: int | None,
    pixel_col: int | None,
) -> dict[str, Any]:
    """Build the compact audit document (does not write files)."""
    array = np.asarray(tensor)
    if array.ndim == 4:
        array = array[0]
    if array.ndim != 3:
        raise ValueError(f"tensor must be (C,H,W); got {array.shape}")
    names = list(channel_names) if channel_names else list(CHANNEL_NAMES)
    if len(names) != int(array.shape[0]):
        # Prefer tensor length; fall back to Stage 2.5 names when exact match.
        if int(array.shape[0]) == CHANNEL_COUNT:
            names = list(CHANNEL_NAMES)
        else:
            names = [f"channel_{i}" for i in range(int(array.shape[0]))]
    height, width = int(array.shape[1]), int(array.shape[2])
    row = int(pixel_row) if pixel_row is not None else height // 2
    col = int(pixel_col) if pixel_col is not None else width // 2
    if not (0 <= row < height and 0 <= col < width):
        row, col = height // 2, width // 2
    query = sample_query_pixel_vector(
        array, channel_names=names, pixel_row=row, pixel_col=col
    )
    meta = dict(acquisition_meta or {})
    sources = meta.get("sources") if isinstance(meta.get("sources"), dict) else {}
    return {
        "schema_version": "ssri.assessment_acquisition_evidence.v1",
        "assessment_id": assessment_id,
        "request_id": request_id,
        "channel_count": int(array.shape[0]),
        "channel_names": names,
        "channel_order_contract": list(CHANNEL_NAMES),
        "tensor_shape": [int(array.shape[0]), height, width],
        "dtype": str(array.dtype),
        "nodata_sentinel": float(FEATURE_NODATA),
        "query_pixel": query,
        "acquisition_provenance": {
            "sources": sources,
            "bbox": meta.get("bbox"),
            "resolution_m": meta.get("resolution_m"),
            "start_date": meta.get("start_date"),
            "end_date": meta.get("end_date"),
            "crs": meta.get("crs"),
            "transform": meta.get("transform"),
        },
        "grid": {
            "crs": meta.get("crs")
            or ((location_provenance or {}).get("model_grid") or {}).get("crs"),
            "transform": meta.get("transform")
            or ((location_provenance or {}).get("model_grid") or {}).get("transform"),
            "width": width,
            "height": height,
            "resolution_m": meta.get("resolution_m")
            or ((location_provenance or {}).get("model_grid") or {}).get("resolution_m"),
        },
        "aoi": {
            "location_provenance": dict(location_provenance or {}),
            "acquisition_bbox": meta.get("bbox"),
            "pixel_row": row,
            "pixel_col": col,
        },
        "checkpoint": {
            "checkpoint_id": checkpoint_id,
            "checkpoint_sha256": checkpoint_sha256,
        },
        "artifacts": {},
        "scientific_validation_status": "NOT_VALIDATED",
        "notes": [
            "Acquisition evidence for auditability only. Status remains NOT_VALIDATED.",
            "TMI / catalogue overlays are not part of the 13-channel inference tensor.",
        ],
    }


def persist_acquisition_evidence(
    *,
    output_root: Path,
    assessment_id: str,
    request_id: str | None,
    tensor: np.ndarray | Any,
    channel_names: Sequence[str] | None,
    acquisition_meta: Mapping[str, Any] | None,
    location_provenance: Mapping[str, Any] | None,
    checkpoint_id: str | None,
    checkpoint_sha256: str | None,
    pixel_row: int | None,
    pixel_col: int | None,
) -> dict[str, Any]:
    """Write tensor + evidence JSON atomically and mirror to object storage."""
    if hasattr(tensor, "detach"):
        array = tensor.detach().cpu().numpy()
    else:
        array = np.asarray(tensor)
    if array.ndim == 4:
        array = array[0]
    array = np.asarray(array, dtype=np.float32)

    acq = acquisition_dir(output_root, assessment_id)
    acq.mkdir(parents=True, exist_ok=True)

    evidence = build_acquisition_evidence(
        assessment_id=assessment_id,
        request_id=request_id,
        tensor=array,
        channel_names=channel_names,
        acquisition_meta=acquisition_meta,
        location_provenance=location_provenance,
        checkpoint_id=checkpoint_id,
        checkpoint_sha256=checkpoint_sha256,
        pixel_row=pixel_row,
        pixel_col=pixel_col,
    )

    tensor_path = acq / TENSOR_FILENAME
    # Prefer keeping an already-written acquisition stack from build_feature_stack.
    if not tensor_path.is_file():
        with tempfile.NamedTemporaryFile(
            prefix=".feature_stack.",
            suffix=".npy",
            dir=str(acq),
            delete=False,
        ) as tmp:
            tmp_path = Path(tmp.name)
            np.save(tmp_path, array)
            tmp.flush()
            os.fsync(tmp.fileno())
        tmp_path.replace(tensor_path)

    tensor_sha = _sha256_file(tensor_path)
    vector_payload = json.dumps(
        evidence["query_pixel"], indent=2, sort_keys=True
    ).encode("utf-8")
    vector_path = acq / QUERY_VECTOR_FILENAME
    _atomic_write_bytes(vector_path, vector_payload)
    vector_sha = _sha256_bytes(vector_payload)

    evidence["artifacts"] = {
        TENSOR_FILENAME: {
            "sha256": tensor_sha,
            "bytes": tensor_path.stat().st_size,
            "object_key": assessment_evidence_object_key(assessment_id, TENSOR_FILENAME),
        },
        QUERY_VECTOR_FILENAME: {
            "sha256": vector_sha,
            "bytes": len(vector_payload),
            "object_key": assessment_evidence_object_key(
                assessment_id, QUERY_VECTOR_FILENAME
            ),
        },
        EVIDENCE_FILENAME: {
            "object_key": assessment_evidence_object_key(assessment_id, EVIDENCE_FILENAME),
        },
    }

    evidence_text = json.dumps(evidence, indent=2, sort_keys=True)
    evidence_bytes = evidence_text.encode("utf-8")
    evidence["artifacts"][EVIDENCE_FILENAME]["sha256"] = _sha256_bytes(evidence_bytes)
    evidence["artifacts"][EVIDENCE_FILENAME]["bytes"] = len(evidence_bytes)
    # Re-serialize with checksum fields populated.
    evidence_text = json.dumps(evidence, indent=2, sort_keys=True)
    evidence_path = acq / EVIDENCE_FILENAME
    _atomic_write_text(evidence_path, evidence_text)

    try:
        from ssri_model.storage.durable import mirror_assessment_acquisition_evidence

        mirror_assessment_acquisition_evidence(acq, assessment_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "assessment_evidence_mirror_failed assessment_id=%s err=%s",
            assessment_id,
            type(exc).__name__,
        )

    return evidence


def load_acquisition_evidence(
    output_root: Path,
    assessment_id: str,
    *,
    materialize: bool = True,
) -> dict[str, Any] | None:
    """Load evidence JSON locally, optionally materializing from object storage."""
    acq = acquisition_dir(output_root, assessment_id)
    path = acq / EVIDENCE_FILENAME
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    if not materialize:
        return None
    try:
        from ssri_model.storage.durable import ensure_assessment_acquisition_evidence_local

        ensure_assessment_acquisition_evidence_local(acq, assessment_id)
    except Exception:
        return None
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def evidence_status_for_assessment(
    output_root: Path,
    assessment_id: str,
) -> dict[str, Any]:
    """Summarize evidence availability without fabricating missing history."""
    evidence = load_acquisition_evidence(output_root, assessment_id, materialize=True)
    acq = acquisition_dir(output_root, assessment_id)
    tensor_path = acq / TENSOR_FILENAME
    if evidence is None:
        return {
            "available": False,
            "historical_gap": True,
            "detail": (
                "No durable acquisition evidence is available for this assessment. "
                "Assessments created before evidence persistence cannot recover "
                "fabricated channel values."
            ),
            "evidence": None,
            "tensor_present": tensor_path.is_file(),
        }
    return {
        "available": True,
        "historical_gap": False,
        "detail": "Acquisition evidence is available.",
        "evidence": evidence,
        "tensor_present": tensor_path.is_file(),
    }
