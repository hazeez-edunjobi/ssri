"""Background job workers for async API execution."""

from __future__ import annotations

from typing import Any

from ssri_model.api.dependencies import BatchExecutor, InferenceExecutor
from ssri_model.jobs.service import JobService
from ssri_model.service.requests import BatchInferenceRequest, InferenceRequest


def run_inference_job(
    *,
    job_service: JobService,
    inference_executor: InferenceExecutor,
    job_id: str,
    request: InferenceRequest,
    scientific_validation_status: str,
    principal_key_id: str,
    auth_role: str,
) -> None:
    from ssri_model.auth.models import AuthenticatedPrincipal, Role
    from ssri_model.auth.authorization import permissions_for_role

    principal = AuthenticatedPrincipal(
        key_id=principal_key_id,
        role=Role(auth_role),
        permissions=permissions_for_role(Role(auth_role)),
        authentication_method="api_key",
        authenticated_at="",
    )
    try:
        response, provenance = inference_executor.execute(
            request,
            scientific_validation_status=scientific_validation_status,
            principal=principal,
        )
        job_service.mark_completed(
            job_id,
            result={
                "request_id": response.request_id,
                "status": response.status.value,
                "prediction_path": response.prediction_path,
                "confidence_path": response.confidence_path,
                "probability_path": response.probability_path,
                "metadata_path": response.metadata_path,
                "scientific_validation_status": response.scientific_validation_status,
                "provenance": provenance.to_dict(),
            },
        )
    except Exception:
        job_service.mark_failed(
            job_id,
            error_code="INFERENCE_FAILED",
            error_message="Inference job failed.",
        )


def run_batch_job(
    *,
    job_service: JobService,
    batch_executor: BatchExecutor,
    job_id: str,
    request: BatchInferenceRequest,
    scientific_validation_status: str,
) -> None:
    try:
        response = batch_executor.execute(
            request,
            scientific_validation_status=scientific_validation_status,
        )
        job_service.mark_completed(
            job_id,
            result={
                "request_id": response.request_id,
                "batch_id": response.batch_id,
                "status": response.status.value,
                "total_jobs": response.total_jobs,
                "completed_jobs": response.completed_jobs,
                "failed_jobs": response.failed_jobs,
                "skipped_jobs": response.skipped_jobs,
                "manifest_path": response.manifest_path,
                "scientific_validation_status": response.scientific_validation_status,
            },
        )
    except Exception:
        job_service.mark_failed(
            job_id,
            error_code="BATCH_FAILED",
            error_message="Batch job failed.",
        )


def _run_release_shell_multiseed_training(
    *,
    storage: Any,
    registry: Any,
    job_id: str,
    payload: dict,
) -> dict:
    """Train ≥3 seeds, evaluate each, aggregate gates, embed shell meta."""
    import hashlib
    import json
    from pathlib import Path

    from ssri_model.manual_training.runner import run_manual_training
    from ssri_model.release_shell.evaluate import evaluate_checkpoint_on_held_out
    from ssri_model.release_shell.shell_finalize import finalize_checkpoint
    from ssri_model.release_shell.validator import validate_release_shell_dataset

    seeds = list(payload.get("release_shell_seeds") or [42, 43, 44])
    if len(seeds) < 3:
        seeds = [42, 43, 44]
    dataset_id = str(payload["dataset_id"])
    base_run = str(payload["run_id"])
    dataset_root = Path(storage.get_dataset(dataset_id).root_path)
    validation_report = validate_release_shell_dataset(dataset_root)
    split_path = dataset_root / "split_manifest.json"
    split_manifest = (
        json.loads(split_path.read_text(encoding="utf-8")) if split_path.exists() else None
    )
    data_hash = hashlib.sha256((dataset_root / "manifest.json").read_bytes()).hexdigest().upper()

    per_seed_results: dict[str, dict] = {}
    per_seed_evals: dict[str, dict] = {}
    primary = None
    for seed in seeds:
        run_id = f"{base_run}_seed{seed}"
        storage.write_progress(
            base_run,
            {
                "phase": "training",
                "message": f"Training seed {seed} ({seeds.index(seed)+1}/{len(seeds)}).",
                "seed": seed,
            },
        )
        seed_result = run_manual_training(
            storage=storage,
            registry=registry,
            dataset_id=dataset_id,
            run_id=run_id,
            job_id=job_id,
            epochs=int(payload.get("epochs", 20)),
            batch_size=int(payload.get("batch_size", 4)),
            learning_rate=float(payload.get("learning_rate", 1e-3)),
            seed=int(seed),
            early_stopping_patience=payload.get("early_stopping_patience"),
            model_name=(
                f"{payload.get('model_name') or 'ssri'}-seed{seed}"
                if payload.get("model_name")
                else None
            ),
            device=str(payload.get("device", "cpu")),
        )
        ev = evaluate_checkpoint_on_held_out(
            dataset_root=dataset_root,
            checkpoint_path=seed_result["checkpoint_path"],
            split_manifest=split_manifest,
            seeds_note=[seed],
        )
        per_seed_results[str(seed)] = seed_result
        per_seed_evals[str(seed)] = ev
        if primary is None:
            primary = seed_result

    assert primary is not None
    meta = finalize_checkpoint(
        primary["checkpoint_path"],
        dataset_root=dataset_root,
        validation_report=validation_report,
        per_seed_evals=per_seed_evals,
        seeds=seeds,
        primary_seed=int(seeds[0]),
        data_hash=data_hash,
    )
    eval_path = (
        Path(primary["checkpoint_path"]).resolve().parent / "release_shell_evaluation.json"
    )
    aggregate = {
        "status": "completed",
        "scientific_validation_status": "NOT_VALIDATED",
        "seeds": seeds,
        "per_seed": per_seed_evals,
        "hazards": meta.get("hazards"),
        "training_region": meta.get("training_region"),
        "primary_checkpoint": primary["checkpoint_path"],
        "score_framing": "relative susceptibility rankings",
    }
    eval_path.write_text(json.dumps(aggregate, indent=2), encoding="utf-8")
    (
        storage.run_dir(base_run) / "release_shell_evaluation.json"
    ).write_text(eval_path.read_text(encoding="utf-8"), encoding="utf-8")
    storage.write_progress(
        base_run,
        {
            "phase": "evaluated",
            "message": (
                f"Trained {len(seeds)} seeds; held-out evaluation complete. "
                "Status remains NOT_VALIDATED."
            ),
            "evaluation_path": str(eval_path),
            "seeds": seeds,
        },
    )
    return {
        **primary,
        "seeds": seeds,
        "per_seed_models": {
            s: {
                "model_id": per_seed_results[s]["model_id"],
                "checkpoint_path": per_seed_results[s]["checkpoint_path"],
            }
            for s in per_seed_results
        },
        "evaluation": aggregate,
        "evaluation_path": str(eval_path),
        "release_shell_meta": meta,
    }


def run_training_job(
    *,
    job_service: JobService,
    job_id: str,
    payload: dict,
) -> None:
    """Execute a manual Stage 2.5 training job."""
    from ssri_model.manual_training.exceptions import ManualTrainingError
    from ssri_model.manual_training.registry import ModelRegistry
    from ssri_model.manual_training.runner import run_manual_training
    from ssri_model.manual_training.storage import TrainingStorage

    output_root = str(payload.get("output_root") or "outputs/service")
    storage = TrainingStorage(output_root)
    registry = ModelRegistry(storage)
    try:
        if payload.get("release_shell_eval"):
            result = _run_release_shell_multiseed_training(
                storage=storage,
                registry=registry,
                job_id=job_id,
                payload=payload,
            )
        else:
            result = run_manual_training(
                storage=storage,
                registry=registry,
                dataset_id=str(payload["dataset_id"]),
                run_id=str(payload["run_id"]),
                job_id=job_id,
                epochs=int(payload.get("epochs", 20)),
                batch_size=int(payload.get("batch_size", 4)),
                learning_rate=float(payload.get("learning_rate", 1e-3)),
                seed=int(payload.get("seed", 42)),
                early_stopping_patience=payload.get("early_stopping_patience"),
                model_name=payload.get("model_name"),
                device=str(payload.get("device", "cpu")),
            )
        job_service.mark_completed(job_id, result=result)
    except ManualTrainingError as exc:
        storage.write_progress(
            str(payload.get("run_id") or "unknown"),
            {
                "phase": "failed",
                "message": exc.message,
                "error_code": exc.code,
            },
        )
        job_service.mark_failed(
            job_id,
            error_code=exc.code,
            error_message=exc.message,
        )
    except Exception:
        job_service.mark_failed(
            job_id,
            error_code="TRAINING_FAILED",
            error_message=(
                "Training failed unexpectedly. See server logs for technical details."
            ),
        )
