"""SSRI scientific validation and dataset integrity."""

from ssri_model.scientific.cli import main
from ssri_model.scientific.config import ScientificValidationConfig
from ssri_model.scientific.dataset_audit import DatasetAuditResult, audit_dataset
from ssri_model.scientific.distribution import (
    ClassDistributionResult,
    DistributionAnalysisResult,
    analyze_class_distribution,
    analyze_distributions,
)
from ssri_model.scientific.exceptions import (
    DatasetAuditError,
    FeatureAuditError,
    InvalidScientificConfigError,
    LabelAuditError,
    ReviewValidationError,
    ScientificValidationError,
    SpatialValidationError,
    ValidationFailureError,
)
from ssri_model.scientific.feature_audit import FeatureAuditResult, audit_features
from ssri_model.scientific.labels import LabelAuditResult, audit_labels
from ssri_model.scientific.leakage import (
    IndependenceReport,
    check_feature_label_leakage,
    validate_dataset_independence,
)
from ssri_model.scientific.report import (
    SCIENTIFIC_VALIDATION_JSON,
    SCIENTIFIC_VALIDATION_MD,
    ScientificReviewRecord,
    ScientificValidationReport,
    attach_review,
    save_scientific_validation_json,
    save_scientific_validation_markdown,
)
from ssri_model.scientific.spatial import (
    SpatialValidationResult,
    check_spatial_overlap,
    compute_spatial_distance,
    validate_spatial_splits,
)
from ssri_model.scientific.validation import (
    audit_dataset_only,
    audit_features_only,
    audit_labels_only,
    audit_spatial_only,
    compute_reproducibility_fingerprints,
    run_scientific_validation,
)

__all__ = [
    "SCIENTIFIC_VALIDATION_JSON",
    "SCIENTIFIC_VALIDATION_MD",
    "ClassDistributionResult",
    "DatasetAuditError",
    "DatasetAuditResult",
    "DistributionAnalysisResult",
    "FeatureAuditError",
    "FeatureAuditResult",
    "IndependenceReport",
    "InvalidScientificConfigError",
    "LabelAuditError",
    "LabelAuditResult",
    "ReviewValidationError",
    "ScientificReviewRecord",
    "ScientificValidationConfig",
    "ScientificValidationError",
    "ScientificValidationReport",
    "SpatialValidationError",
    "SpatialValidationResult",
    "ValidationFailureError",
    "analyze_class_distribution",
    "analyze_distributions",
    "attach_review",
    "audit_dataset",
    "audit_dataset_only",
    "audit_features",
    "audit_features_only",
    "audit_labels",
    "audit_labels_only",
    "audit_spatial_only",
    "check_feature_label_leakage",
    "check_spatial_overlap",
    "compute_reproducibility_fingerprints",
    "compute_spatial_distance",
    "main",
    "run_scientific_validation",
    "save_scientific_validation_json",
    "save_scientific_validation_markdown",
    "validate_dataset_independence",
    "validate_spatial_splits",
]
