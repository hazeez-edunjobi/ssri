"""Jobs GET must expose training result and progress in one place."""

from __future__ import annotations

from fastapi.testclient import TestClient

from ssri_model.api.app import create_app
from ssri_model.auth.authorization import permissions_for_role
from ssri_model.auth.models import AuthenticatedPrincipal, Role
from ssri_model.jobs.models import JobStatus, JobType
from ssri_model.manual_training.storage import TrainingStorage
from tests.api_helpers import build_api_config


def test_jobs_get_includes_result_and_progress(tmp_path, monkeypatch):
    monkeypatch.setenv("SSRI_RELEASE_SHELL", "true")
    cfg = build_api_config(tmp_path)
    app = create_app(cfg)
    client = TestClient(app)
    service = app.state.ssri.job_service
    # Match development_principal() so unauthenticated TestClient can GET the job.
    principal = AuthenticatedPrincipal(
        key_id="development",
        role=Role.OPERATOR,
        permissions=permissions_for_role(Role.OPERATOR),
        authentication_method="development",
        authenticated_at="2026-01-01T00:00:00+00:00",
    )
    run_id = "run_shelltest01"
    output_root = str(tmp_path / "service-outputs")
    TrainingStorage(output_root).write_progress(
        run_id,
        {"phase": "training", "epoch": 1, "total_epochs": 3, "message": "seed 42"},
    )
    record = service.create_job(
        request_id="req-shell-1",
        job_type=JobType.TRAINING,
        principal=principal,
        scientific_validation_status="NOT_VALIDATED",
        payload={
            "run_id": run_id,
            "dataset_id": "ds1",
            "output_root": output_root,
            "release_shell_eval": True,
        },
    )
    # QUEUED -> RUNNING -> COMPLETED
    store = service._store
    running = store.load(record.job_id)
    running.status = JobStatus.RUNNING
    running.started_at = running.created_at
    store.save(running)
    service.mark_completed(
        record.job_id,
        result={
            "model_id": "mdl_1",
            "checkpoint_path": str(tmp_path / "best.pt"),
            "evaluation": {"aggregate_gates": {"landslide": "evaluated"}},
            "evaluation_path": str(tmp_path / "eval.json"),
            "message": "Trained 3 seeds; held-out evaluation complete.",
        },
    )

    response = client.get(f"/api/v1/jobs/{record.job_id}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == JobStatus.COMPLETED.value
    assert body["result"] is not None
    assert body["result"]["evaluation"]["aggregate_gates"]["landslide"] == "evaluated"
    assert body["artifacts"]["evaluation_path"] == str(tmp_path / "eval.json")
    assert body["progress"] is not None
    assert body["progress"]["phase"] == "training"
