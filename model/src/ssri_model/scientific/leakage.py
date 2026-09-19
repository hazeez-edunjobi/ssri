"""Dataset independence and leakage diagnostics."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np

from ssri_model.scientific.spatial import SplitName, validate_spatial_splits

AuditStatus = Literal["PASS", "WARNING", "FAIL"]


@dataclass
class LeakageFinding:
    """One leakage or independence diagnostic finding."""

    category: str
    suspicious: bool
    feature_name: str | None
    statistic: float | None
    threshold: float | None
    explanation: str


@dataclass
class IndependenceReport:
    """Formal train/test independence report."""

    independent: bool
    sample_id_overlap: list[tuple[str, str, str]] = field(default_factory=list)
    feature_path_overlap: list[tuple[str, str]] = field(default_factory=list)
    label_path_overlap: list[tuple[str, str]] = field(default_factory=list)
    duplicate_feature_hashes: list[tuple[str, str]] = field(default_factory=list)
    duplicate_metadata: list[str] = field(default_factory=list)
    spatial_overlap_count: int = 0
    spatial_buffer_count: int = 0
    findings: list[LeakageFinding] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    status: AuditStatus = "PASS"


def _file_hash(path: Path, *, chunk_size: int = 1024 * 1024) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(chunk_size)
                if not chunk:
                    break
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def _collect_sample_refs(
    dataset_root: Path,
    manifest_payload: dict[str, object],
) -> dict[str, dict[str, object]]:
    splits = manifest_payload.get("splits")
    if not isinstance(splits, dict):
        return {}
    refs: dict[str, dict[str, object]] = {}
    for split_name, sample_ids in splits.items():
        if not isinstance(sample_ids, list):
            continue
        for sample_id in sample_ids:
            sample_dir = dataset_root / str(split_name) / str(sample_id)
            metadata_path = sample_dir / "metadata.json"
            metadata: dict[str, object] = {}
            if metadata_path.exists():
                import json

                try:
                    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    metadata = {}
            refs[str(sample_id)] = {
                "split": str(split_name),
                "feature_path": str(sample_dir / "feature_stack.npy"),
                "label_path": str(sample_dir / "label.tif"),
                "metadata_path": str(metadata_path),
                "metadata": metadata,
            }
    return refs


def check_feature_label_leakage(
    dataset_root: Path,
    manifest_payload: dict[str, object],
    *,
    max_correlation: float = 0.99,
) -> list[LeakageFinding]:
    from ssri_model.ml.constants import CHANNEL_NAMES, FEATURE_NODATA

    findings: list[LeakageFinding] = []
    refs = _collect_sample_refs(dataset_root, manifest_payload)

    for sample_id, ref in refs.items():
        feature_path = Path(str(ref["feature_path"]))
        label_path = Path(str(ref["label_path"]))
        if "label" in feature_path.name.lower() and feature_path.name != "feature_stack.npy":
            findings.append(
                LeakageFinding(
                    category="path",
                    suspicious=True,
                    feature_name=None,
                    statistic=None,
                    threshold=None,
                    explanation=f"Feature path may contain label artifact: {feature_path}",
                )
            )
        if feature_path.resolve() == label_path.resolve():
            findings.append(
                LeakageFinding(
                    category="path",
                    suspicious=True,
                    feature_name=None,
                    statistic=None,
                    threshold=None,
                    explanation=f"Feature and label paths are identical for {sample_id}",
                )
            )

        if not feature_path.exists() or not label_path.exists():
            continue

        try:
            import rasterio

            tensor = np.load(feature_path, mmap_mode="r")
            with rasterio.open(label_path) as dataset:
                label = dataset.read(1).astype(np.float64)
            valid = label != FEATURE_NODATA
            if not np.any(valid):
                continue
            label_mean = float(np.mean(label[valid]))
            for index, channel_name in enumerate(CHANNEL_NAMES):
                channel = np.asarray(tensor[index])
                channel_valid = channel[channel != FEATURE_NODATA]
                if channel_valid.size == 0:
                    continue
                feature_mean = float(np.mean(channel_valid))
                denom = max(abs(label_mean), abs(feature_mean), 1e-6)
                association = 1.0 - abs(feature_mean - label_mean) / denom
                if association >= max_correlation:
                    findings.append(
                        LeakageFinding(
                            category="association",
                            suspicious=True,
                            feature_name=channel_name,
                            statistic=association,
                            threshold=max_correlation,
                            explanation=(
                                f"Diagnostic: {channel_name} mean association with "
                                f"label mean in {sample_id} exceeds threshold. "
                                "Correlation does not prove leakage."
                            ),
                        )
                    )
        except Exception:
            continue

    return findings


def validate_dataset_independence(
    dataset_root: Path,
    manifest_payload: dict[str, object],
    *,
    spatial_buffer_m: float = 0.0,
    max_train_test_overlap: int = 0,
    max_validation_test_overlap: int = 0,
    max_feature_label_correlation: float = 0.99,
) -> IndependenceReport:
    refs = _collect_sample_refs(dataset_root, manifest_payload)
    report = IndependenceReport(independent=True)

    split_of = {sample_id: str(ref["split"]) for sample_id, ref in refs.items()}
    sample_ids = list(refs.keys())
    for index, sample_a in enumerate(sample_ids):
        for sample_b in sample_ids[index + 1 :]:
            if split_of[sample_a] != split_of[sample_b]:
                if sample_a == sample_b:
                    report.sample_id_overlap.append((sample_a, sample_b, "duplicate_id"))
                    report.independent = False
                    report.reasons.append(f"Duplicate sample ID across splits: {sample_a}")

    feature_paths: dict[str, str] = {}
    label_paths: dict[str, str] = {}
    feature_hashes: dict[str, str] = {}
    metadata_hashes: dict[str, str] = {}

    for sample_id, ref in refs.items():
        feature_path = str(ref["feature_path"])
        label_path = str(ref["label_path"])
        if feature_path in feature_paths.values():
            other = next(key for key, value in feature_paths.items() if value == feature_path)
            report.feature_path_overlap.append((sample_id, other))
            report.independent = False
            report.reasons.append(f"Duplicate feature path: {sample_id}, {other}")
        feature_paths[sample_id] = feature_path

        if label_path in label_paths.values():
            other = next(key for key, value in label_paths.items() if value == label_path)
            report.label_path_overlap.append((sample_id, other))
            report.independent = False
            report.reasons.append(f"Duplicate label path: {sample_id}, {other}")
        label_paths[sample_id] = label_path

        feature_hash = _file_hash(Path(feature_path))
        if feature_hash:
            if feature_hash in feature_hashes.values():
                other = next(
                    key for key, value in feature_hashes.items() if value == feature_hash
                )
                if split_of[sample_id] != split_of[other]:
                    report.duplicate_feature_hashes.append((sample_id, other))
                    report.independent = False
                    report.reasons.append(
                        f"Duplicate feature hash across splits: {sample_id}, {other}"
                    )
            feature_hashes[sample_id] = feature_hash

        metadata_path = Path(str(ref["metadata_path"]))
        metadata_hash = _file_hash(metadata_path)
        if metadata_hash:
            if metadata_hash in metadata_hashes.values():
                report.duplicate_metadata.append(sample_id)
            metadata_hashes[sample_id] = metadata_hash

    samples_by_split: dict[SplitName, dict[str, dict[str, object]]] = {
        "train": {},
        "validation": {},
        "test": {},
    }
    for sample_id, ref in refs.items():
        metadata = ref.get("metadata")
        if isinstance(metadata, dict):
            split_key = split_of[sample_id]
            if split_key in samples_by_split:
                samples_by_split[split_key][sample_id] = metadata

    spatial = validate_spatial_splits(
        samples_by_split,
        spatial_buffer_m=spatial_buffer_m,
        max_train_test_overlap=max_train_test_overlap,
        max_validation_test_overlap=max_validation_test_overlap,
    )
    report.spatial_overlap_count = len(spatial.overlapping_samples)
    report.spatial_buffer_count = len(spatial.buffered_samples)
    if spatial.status == "FAIL":
        report.independent = False
        report.status = "FAIL"
        report.reasons.extend(spatial.messages)
    elif spatial.status == "WARNING" and report.status == "PASS":
        report.status = "WARNING"
        report.reasons.extend(spatial.messages)

    leakage_findings = check_feature_label_leakage(
        dataset_root,
        manifest_payload,
        max_correlation=max_feature_label_correlation,
    )
    report.findings.extend(leakage_findings)
    suspicious = [finding for finding in leakage_findings if finding.suspicious]
    if suspicious and report.status == "PASS":
        report.status = "WARNING"
        report.reasons.append(
            f"{len(suspicious)} suspicious feature/label association diagnostics detected"
        )

    splits = manifest_payload.get("splits")
    if isinstance(splits, dict):
        train = {str(value) for value in splits.get("train", [])}
        validation = {str(value) for value in splits.get("validation", [])}
        test = {str(value) for value in splits.get("test", [])}
        for label, overlap in (
            ("train/validation", train & validation),
            ("train/test", train & test),
            ("validation/test", validation & test),
        ):
            if overlap:
                report.independent = False
                report.status = "FAIL"
                report.reasons.append(
                    f"Sample ID overlap between {label}: {sorted(overlap)}"
                )

    return report
