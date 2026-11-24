"""One-shot local runner: Abeokuta candidate magnetic lineament extraction."""

from __future__ import annotations

import json
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "outputs"


def main() -> int:
    print("ROOT", ROOT, flush=True)
    try:
        from ssri_model.geological.durable import build_geological_storage
        from ssri_model.geological.service import GeologicalService
        from ssri_model.evaluation.subsidence_validation import (
            discover_ground_truth_candidates,
            missing_ground_truth_report,
            write_schema_stub,
        )
        from ssri_model.geological.conditioning_inventory import conditioning_factor_inventory

        storage = build_geological_storage(OUT)
        svc = GeologicalService(storage)
        print("Extracting…", flush=True)
        _rec, report = svc.extract_candidate_lineaments(
            "geo_be00a34ad6f4", percentile=92.0
        )
        stats = report.get("statistics") or {}
        print("n_lineaments", stats.get("n_lineaments"), flush=True)
        print("circular_mean_az", stats.get("circular_mean_azimuth_deg"), flush=True)
        print("length", stats.get("length_m"), flush=True)
        lin = (
            OUT
            / "geological"
            / "datasets"
            / "geo_be00a34ad6f4"
            / "working"
            / "derived"
            / "lineaments"
        )
        print("artifacts", sorted(p.name for p in lin.glob("*")), flush=True)
        summary = {
            "geo_id": "geo_be00a34ad6f4",
            "statistics": stats,
            "qc_relpath": str(
                lin / "lineament_extraction_qc.json"
            ).replace("\\", "/"),
            "scientific_validation_status": "NOT_VALIDATED",
            "not_confirmed_faults_or_fractures": True,
            "used_in_inference": False,
        }
        (ROOT / "poc" / "abeokuta_candidate_lineament_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        stub = write_schema_stub(
            OUT / "validation" / "subsidence_ground_truth_schema.json"
        )
        found = discover_ground_truth_candidates(ROOT)
        miss = missing_ground_truth_report(
            checkpoint_id="ssri-model-e7af3afcd0",
            searched_paths=[c["path"] for c in found],
        )
        (ROOT / "poc" / "subsidence_validation_missing_report.json").write_text(
            json.dumps(miss, indent=2), encoding="utf-8"
        )
        (ROOT / "poc" / "conditioning_factor_inventory.json").write_text(
            json.dumps(conditioning_factor_inventory(), indent=2), encoding="utf-8"
        )
        print("schema stub", stub, flush=True)
        print("done", flush=True)
        return 0
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
