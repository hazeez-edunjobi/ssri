"""Scientific validation orchestration and reproducibility fingerprints."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import cast

from ssri_model import __version__
from ssri_model.dataset.catalog import load_catalog_manifest
from ssri_model.scientific.config import ScientificValidationConfig
from ssri_model.scientific.dataset_audit import DatasetAuditResult, audit_dataset
from ssri_model.scientific.distribution import analyze_distributions
from ssri_model.scientific.feature_audit import FeatureAuditResult, audit_features
from ssri_model.scientific.labels import LabelAuditResult, audit_labels
from ssri_model.scientific.leakage import IndependenceReport, validate_dataset_independence
from ssri_model.scientific.report import (
    SCIENTIFIC_VALIDATION_JSON,
    SCIENTIFIC_VALIDATION_MD,
    ScientificValidationReport,
    save_scientific_validation_json,
    save_scientific_validation_markdown,
)
from ssri_model.scientific.spatial import SpatialValidationResult, validate_spatial_splits


def _hash_file(path: Path) -> str:
    if not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def compute_reproducibility_fingerprints(
    *,
    manifest_path: Path,
    statistics_path: Path | None = None,
    checkpoint_path: Path | None = None,
    config: ScientificValidationConfig | None = None,
) -> dict[str, str]:
    cfg = config or ScientificValidationConfig()
    stats_path = statistics_path or manifest_path.parent / "statistics.json"
    dataset_fingerprint = _hash_file(manifest_path)
    statistics_fingerprint = _hash_file(stats_path) if stats_path.exists() else ""
    checkpoint_fingerprint = _hash_file(checkpoint_path) if checkpoint_path else ""
    configuration_fingerprint = hashlib.sha256(
        json.dumps(asdict(cfg), sort_keys=True).encode("utf-8")
    ).hexdigest()
    combined = hashlib.sha256(
        "|".join(
            [
                dataset_fingerprint,
                statistics_fingerprint,
                checkpoint_fingerprint,
                configuration_fingerprint,
                __version__,
                str(cfg.random_seed),
            ]
        ).encode("utf-8")
    ).hexdigest()
    return {
        "dataset_fingerprint": dataset_fingerprint,
        "statistics_fingerprint": statistics_fingerprint,
        "checkpoint_fingerprint": checkpoint_fingerprint,
        "configuration_fingerprint": configuration_fingerprint,
        "combined_fingerprint": combined,
        "package_version": __version__,
    }


def _collect_metadata_by_split(
    dataset_root: Path,
    manifest_payload: dict[str, object],
) -> dict[str, dict[str, dict[str, object]]]:
    splits = manifest_payload.get("splits")
    result: dict[str, dict[str, dict[str, object]]] = {
        "train": {},
        "validation": {},
        "test": {},
    }
    if not isinstance(splits, dict):
        return result
    for split_name, sample_ids in splits.items():
        if split_name not in result or not isinstance(sample_ids, list):
            continue
        for sample_id in sample_ids:
            metadata_path = dataset_root / str(split_name) / str(sample_id) / "metadata.json"
            if metadata_path.exists():
                try:
                    result[split_name][str(sample_id)] = json.loads(
                        metadata_path.read_text(encoding="utf-8")
                    )
                except (OSError, json.JSONDecodeError):
                    continue
    return result


def _determine_automated_status(
    *,
    dataset_status: str,
    label_status: str,
    feature_status: str,
    spatial_status: str,
    independence: IndependenceReport,
    distribution_status: str,
) -> str:
    if any(
        status == "FAIL"
        for status in (
            dataset_status,
            label_status,
            feature_status,
            spatial_status,
            independence.status,
            distribution_status,
        )
    ):
        return "NOT_VALIDATED"
    if (
        spatial_status == "PASS"
        and independence.independent
        and independence.spatial_overlap_count == 0
    ):
        return "SPATIALLY_VALIDATED"
    if all(
        status in ("PASS", "WARNING")
        for status in (dataset_status, label_status, feature_status, distribution_status)
    ):
        return "DATASET_AUDITED"
    return "NOT_VALIDATED"


def run_scientific_validation(
    *,
    manifest_path: Path | str,
    statistics_path: Path | str | None = None,
    output_dir: Path | str | None = None,
    config: ScientificValidationConfig | None = None,
    checkpoint_path: Path | str | None = None,
) -> ScientificValidationReport:
    cfg = config or ScientificValidationConfig()
    manifest_file = Path(manifest_path)
    dataset_root = manifest_file.parent
    stats_path = (
        Path(statistics_path)
        if statistics_path
        else dataset_root / "statistics.json"
    )
    out_dir = Path(output_dir) if output_dir else dataset_root / "scientific_validation"

    dataset_audit = audit_dataset(
        manifest_path=manifest_file,
        statistics_path=stats_path,
    )
    payload = cast(dict[str, object], load_catalog_manifest(manifest_file))
    label_audit = audit_labels(dataset_root, payload, config=cfg)
    feature_audit = audit_features(dataset_root, payload, config=cfg)
    distribution = analyze_distributions(dataset_root, payload, label_audit, config=cfg)
    metadata_by_split = _collect_metadata_by_split(dataset_root, payload)
    spatial = validate_spatial_splits(
        metadata_by_split,  # type: ignore[arg-type]
        spatial_buffer_m=cfg.spatial_buffer_m,
        max_train_test_overlap=cfg.max_train_test_overlap,
        max_validation_test_overlap=cfg.max_validation_test_overlap,
    )
    independence = validate_dataset_independence(
        dataset_root,
        payload,
        spatial_buffer_m=cfg.spatial_buffer_m,
        max_train_test_overlap=cfg.max_train_test_overlap,
        max_validation_test_overlap=cfg.max_validation_test_overlap,
        max_feature_label_correlation=cfg.max_feature_label_correlation,
    )
    fingerprints = compute_reproducibility_fingerprints(
        manifest_path=manifest_file,
        statistics_path=stats_path,
        checkpoint_path=Path(checkpoint_path) if checkpoint_path else None,
        config=cfg,
    )

    automated_status = _determine_automated_status(
        dataset_status=dataset_audit.status,
        label_status=label_audit.status,
        feature_status=feature_audit.status,
        spatial_status=spatial.status,
        independence=independence,
        distribution_status=distribution.status,
    )

    report = ScientificValidationReport(
        status=automated_status,  # type: ignore[arg-type]
        scientific_validation_status=automated_status,
        dataset={
            "name": dataset_audit.dataset_name,
            "version": dataset_audit.dataset_version,
            "sample_count": dataset_audit.sample_count,
            "crs": dataset_audit.crs,
            "resolution": dataset_audit.resolution,
        },
        audits={
            "dataset_integrity": dataset_audit.status,
            "label_integrity": label_audit.status,
            "feature_integrity": feature_audit.status,
            "spatial_independence": spatial.status,
            "distribution_shift": distribution.status,
            "independence": independence.status,
        },
        warnings=[
            *dataset_audit.warnings,
            *label_audit.warnings,
            *feature_audit.warnings,
            *distribution.warnings,
            *spatial.messages,
            *independence.reasons,
        ],
        fingerprints=fingerprints,
        independence={
            "independent": independence.independent,
            "spatial_overlap_count": independence.spatial_overlap_count,
            "spatial_buffer_count": independence.spatial_buffer_count,
            "reasons": independence.reasons,
        },
        distribution={
            "max_min_class_ratio": distribution.class_distribution.max_min_class_ratio,
            "feature_shift_warnings": [
                warning
                for shift in distribution.feature_shifts
                for warning in shift.warnings
            ],
        },
        scientific_review_required=True,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    save_scientific_validation_json(out_dir / SCIENTIFIC_VALIDATION_JSON, report)
    save_scientific_validation_markdown(out_dir / SCIENTIFIC_VALIDATION_MD, report)
    return report


def audit_dataset_only(
    *,
    manifest_path: Path | str,
    statistics_path: Path | str | None = None,
) -> DatasetAuditResult:
    return audit_dataset(manifest_path=manifest_path, statistics_path=statistics_path)


def audit_spatial_only(
    *,
    manifest_path: Path | str,
    config: ScientificValidationConfig | None = None,
) -> SpatialValidationResult:
    cfg = config or ScientificValidationConfig()
    manifest_file = Path(manifest_path)
    payload = cast(dict[str, object], load_catalog_manifest(manifest_file))
    metadata_by_split = _collect_metadata_by_split(manifest_file.parent, payload)
    return validate_spatial_splits(
        metadata_by_split,  # type: ignore[arg-type]
        spatial_buffer_m=cfg.spatial_buffer_m,
        max_train_test_overlap=cfg.max_train_test_overlap,
        max_validation_test_overlap=cfg.max_validation_test_overlap,
    )


def audit_labels_only(
    *,
    manifest_path: Path | str,
    config: ScientificValidationConfig | None = None,
) -> LabelAuditResult:
    cfg = config or ScientificValidationConfig()
    manifest_file = Path(manifest_path)
    payload = cast(dict[str, object], load_catalog_manifest(manifest_file))
    return audit_labels(manifest_file.parent, payload, config=cfg)


def audit_features_only(
    *,
    manifest_path: Path | str,
    config: ScientificValidationConfig | None = None,
) -> FeatureAuditResult:
    cfg = config or ScientificValidationConfig()
    manifest_file = Path(manifest_path)
    payload = cast(dict[str, object], load_catalog_manifest(manifest_file))
    return audit_features(manifest_file.parent, payload, config=cfg)
