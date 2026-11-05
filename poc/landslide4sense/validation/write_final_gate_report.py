"""Aggregate phases 1–6 into the release-readiness gate report. No integration."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "validation" / "outputs"
VAL = ROOT / "validation"


def load(name: str) -> dict:
    p = OUT / name
    if not p.exists():
        # nested georef
        p2 = OUT / "georef" / name
        if p2.exists():
            return json.loads(p2.read_text(encoding="utf-8"))
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> None:
    # Ensure phase1 exists
    p1_path = OUT / "phase1_model.json"
    if not p1_path.exists():
        raise SystemExit("run verify_phase1.py first")

    p1 = json.loads(p1_path.read_text(encoding="utf-8"))
    p3 = load("heldout_eval.json")
    p24 = load("georef_report.json")
    if not p24:
        p24 = json.loads((OUT / "georef" / "georef_report.json").read_text(encoding="utf-8"))
    p5 = load("deployment_measure.json")
    crit = json.loads((VAL / "acceptance_criteria.json").read_text(encoding="utf-8"))

    checklist = [
        {
            "criterion": "phase1_model_authenticated",
            "result": "PASS" if p1.get("verdict") == "PASS" else "BLOCKED",
            "evidence": f"SHA256 match={p1.get('sha256_match')}; missing_keys={p1.get('missing')}; source={p1.get('checkpoint_source')}",
        },
        {
            "criterion": "phase2_georeferenced_input_ok",
            "result": "BLOCKED",
            "evidence": p24.get("acceptance", {}).get("phase2_reason")
            or "No defensible distribution-matched 14-band georeferenced stack",
        },
        {
            "criterion": "phase3_held_out_gates_pass",
            "result": "PASS" if p3.get("numeric_gates_pass") else "FAIL",
            "evidence": (
                f"micro_F1={p3.get('metrics', {}).get('model', {}).get('f1')}; "
                f"gates={p3.get('gates')}; scientific_acceptance={p3.get('scientific_acceptance')}"
            ),
        },
        {
            "criterion": "phase3_scientific_validation",
            "result": "UNRESOLVED",
            "evidence": p3.get("scientific_acceptance_note") or "Policy: numeric pass ≠ scientific validation",
        },
        {
            "criterion": "phase4_georeferenced_output_ok",
            "result": "FAIL",
            "evidence": (
                f"CRS written={p24.get('inference', {}).get('crs')}; "
                f"empty_prediction={p24.get('inference', {}).get('qa', {}).get('empty_prediction')}; "
                f"domain_matched={p24.get('inference', {}).get('domain_matched_to_deepslide_training')}; "
                f"{p24.get('acceptance', {}).get('phase4_reason')}"
            ),
        },
        {
            "criterion": "phase5_deployment_feasibility_ok",
            "result": "FAIL",
            "evidence": (
                f"isolated_CPU_ok peak_rss={p5.get('gates', {}).get('peak_rss_mb')} MB; "
                f"live_render_verified={p5.get('gates', {}).get('live_render_verified')}; "
                f"assess_compatible={p5.get('gates', {}).get('assess_route_compatible_without_new_ingest')}"
            ),
        },
        {
            "criterion": "ssri_input_contract_compatible_or_new_pipeline_ready",
            "result": "FAIL",
            "evidence": "SSRI assess uses 13-channel Stage 2.5 stack; DeepSlide needs 14-band L4S. No new ingest pipeline implemented.",
        },
    ]

    # Overall verdict rules from user prompt
    results = {c["criterion"]: c["result"] for c in checklist}
    if any(v == "BLOCKED" for v in results.values() if v != "UNRESOLVED"):
        # phase2 blocked is a necessary dependency
        overall = "BLOCKED"
    elif all(
        results[k] == "PASS"
        for k in (
            "phase1_model_authenticated",
            "phase2_georeferenced_input_ok",
            "phase3_held_out_gates_pass",
            "phase4_georeferenced_output_ok",
            "phase5_deployment_feasibility_ok",
            "ssri_input_contract_compatible_or_new_pipeline_ready",
        )
    ):
        overall = "PASS FOR INTEGRATION"
    else:
        # Have failures without being purely blocked on missing asset
        # Phase2 BLOCKED dominates → already handled. If we treated phase2 as fail:
        overall = "BLOCKED" if results.get("phase2_georeferenced_input_ok") == "BLOCKED" else "FAIL"

    remediations = [
        {
            "priority": 1,
            "action": "Reproduce Landslide4Sense competition band scaling (or retrain/fine-tune DeepSlide on physically unit STAC stacks with spatial-block holdout).",
            "why": "STAC georeferenced stacks are CRS-valid but domain-shifted; georef inference produced empty masks (max sigmoid≈0.01).",
        },
        {
            "priority": 2,
            "action": "Build SSRI 14-band ingest (S2 B1–B12 + DEM/slope) with CRS, replacing reliance on the 13-channel Stage 2.5 stack for landslide-only path.",
            "why": "Assess/worker cannot feed DeepSlide without a new feature pipeline.",
        },
        {
            "priority": 3,
            "action": "Obtain ALOS PALSAR DEM/slope (or justify Copernicus DEM) and a real B10 source if required; keep B10 fill documented.",
            "why": "L4S used ALOS PALSAR; STAC path used Copernicus GLO-30 and zero-filled B10.",
        },
        {
            "priority": 4,
            "action": "After domain-matched georef works, run labelled georeferenced AOI evaluation and a live Render memory/cold-start test with authorization.",
            "why": "Phase 4 map usefulness and Phase 5 production verification remain open.",
        },
        {
            "priority": 5,
            "action": "Do not integrate behind /api/v1/assess until all PASS FOR INTEGRATION gates clear.",
            "why": "Integration gate explicitly forbids partial pass.",
        },
    ]

    report = {
        "title": "SSRI DeepSlide Landslide Integration Gate — Release Readiness",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "overall_verdict": overall,
        "integration_authorized": False,
        "integration_performed": False,
        "scope": "landslide_only",
        "model": {
            "name": "DeepSlide MobileNetV2 U-Net (smp)",
            "checkpoint": str(ROOT / "weights" / "mobilenetv2.pth"),
            "sha256": p1.get("sha256_local"),
            "source": p1.get("checkpoint_source"),
            "license": "MIT",
        },
        "checklist": checklist,
        "held_out_summary": {
            "dataset": "Landslide4Sense validation chips 1–40 (HF ibm-nasa-geospatial)",
            "n_chips": p3.get("test_set", {}).get("n_chips"),
            "prevalence": p3.get("test_set", {}).get("class_prevalence_landslide"),
            "threshold": 0.5,
            "micro": p3.get("metrics", {}).get("model"),
            "majority_f1": p3.get("metrics", {}).get("majority_baseline", {}).get("f1"),
            "slope_f1": p3.get("metrics", {}).get("slope_baseline", {}).get("f1"),
            "numeric_gates_pass": p3.get("numeric_gates_pass"),
            "scientific_acceptance": p3.get("scientific_acceptance"),
        },
        "geographic_inference": {
            "real_crs_geotiff_written": bool(p24.get("inference", {}).get("georeferenced")),
            "crs": p24.get("inference", {}).get("crs"),
            "empty_predictions": p24.get("inference", {}).get("qa", {}).get("empty_prediction"),
            "defensible_domain_match": False,
            "artifacts": {
                "input": p24.get("stack", {}).get("input_tif"),
                "prediction": p24.get("inference", {}).get("prediction_tif"),
                "preview": p24.get("inference", {}).get("preview"),
            },
        },
        "deployment": p5.get("measurements"),
        "deployment_gates": p5.get("gates"),
        "acceptance_criteria": crit,
        "remediation_plan": remediations,
        "limitations": [
            "Landslide only — no subsidence/sinkhole claim",
            "L4S competition chips have no CRS; cannot georeference them honestly",
            "Competition value scaling unpublished; STAC physical units ≠ training domain",
            "Held-out numeric pass on HF validation labels; scientific validation UNRESOLVED",
            "Sigmoid scores are uncalibrated — not risk probabilities",
            "Production Render live test not authorized/executed",
            "SSRI 13-channel assess path incompatible without new ingest",
        ],
    }

    (OUT / "RELEASE_READINESS.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    md = f"""# SSRI DeepSlide Landslide — Release Readiness Report

**Overall verdict: {overall}**  
**Integration authorized: NO** (not performed)

Generated: {report['generated_at_utc']}

## 1. Exact model and checkpoint

| Field | Value |
|-------|-------|
| Model | DeepSlide MobileNetV2 U-Net (`smp.Unet`, 14→1) |
| Checkpoint | `poc/landslide4sense/weights/mobilenetv2.pth` |
| SHA256 | `{p1.get('sha256_local')}` |
| HF LFS match | {p1.get('sha256_match')} |
| License | MIT |
| Source | [harshinde/DeepSlide_Models](https://huggingface.co/harshinde/DeepSlide_Models) |
| Preprocess | NaN→ε; **normalize=False**; sigmoid; threshold **0.5** (DeepSlide default; not tuned on eval) |

## 2. Real geographic inference

| Check | Result |
|-------|--------|
| STAC 14-band stack with CRS | Built (`EPSG:32653`) |
| Domain-matched to DeepSlide training | **NO** (physical units vs L4S competition tensors) |
| Prediction GeoTIFF with real CRS | Written: `validation/outputs/georef/prediction_georef.tif` |
| Useful non-empty mask | **NO** — empty at 0.5 (max score ≈ 0.011) |
| Calibrated risk | **NO** — uncalibrated segmentation score |

## 3. Held-out evaluation

- **Dataset:** Landslide4Sense **validation** chips 1–40 (HF), 655 360 pixels, landslide prevalence ≈ 1.14%
- **Split:** competition validation (held-out from train); not a spatial-block split of an independent inventory
- **Threshold:** fixed 0.5 (author default), declared before eval in `acceptance_criteria.json`

| Method | Precision | Recall | F1 | IoU |
|--------|-----------|--------|----|-----|
| DeepSlide | {p3['metrics']['model']['precision']:.4f} | {p3['metrics']['model']['recall']:.4f} | **{p3['metrics']['model']['f1']:.4f}** | {p3['metrics']['model']['iou']:.4f} |
| Majority | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| Slope heuristic | {p3['metrics']['slope_baseline']['precision']:.4f} | {p3['metrics']['slope_baseline']['recall']:.4f} | {p3['metrics']['slope_baseline']['f1']:.4f} | {p3['metrics']['slope_baseline']['iou']:.4f} |

Confusion (model): TN={p3['metrics']['model']['tn']}, FP={p3['metrics']['model']['fp']}, FN={p3['metrics']['model']['fn']}, TP={p3['metrics']['model']['tp']}

Numeric gates (pre-declared): **PASS** (≥0.50 F1; beat majority; beat slope by ≥0.10).  
**Scientific acceptance: UNRESOLVED** (does not equal production validation).

## 4. Georeferenced map

CRS-aligned GeoTIFF + preview exist under `validation/outputs/georef/`, but they are **not** accepted as a production landslide map because the input domain is wrong and the mask is empty.

## 5. Deployment architecture

| Metric | Value |
|--------|-------|
| Load (CPU) | {p5['measurements']['model_load_s']} s |
| Infer / chip | ~{p5['measurements']['infer_per_chip_s_mean']} s |
| Peak RSS | ~{p5['gates']['peak_rss_mb']:.0f} MB |
| Live Render verified | **NO** |
| Compatible with current `/api/v1/assess` 13-ch stack | **NO** |

Isolated CPU inference is light enough for typical small hosts; wiring into SSRI is not ready.

## 6. Remaining limitations

{chr(10).join('- ' + x for x in report['limitations'])}

## 7. Gate checklist

| Criterion | Result |
|-----------|--------|
"""
    for c in checklist:
        md += f"| {c['criterion']} | **{c['result']}** |\n"

    md += f"""
## Final decision

**{overall}** — Do **not** integrate DeepSlide into SSRI assess/worker.

### Smallest remediation plan
"""
    for r in remediations:
        md += f"{r['priority']}. **{r['action']}** — {r['why']}\n"

    md += """
### Artifacts
- `validation/acceptance_criteria.json` (pre-declared)
- `validation/outputs/phase1_model.json`
- `validation/outputs/heldout_eval.json`
- `validation/outputs/georef/georef_report.json`
- `validation/outputs/deployment_measure.json`
- `validation/outputs/RELEASE_READINESS.json`
"""
    (OUT / "RELEASE_READINESS.md").write_text(md, encoding="utf-8")
    # also copy to poc root for visibility
    (ROOT / "RELEASE_READINESS.md").write_text(md, encoding="utf-8")
    print(json.dumps({"overall_verdict": overall, "integration_authorized": False}, indent=2))


if __name__ == "__main__":
    main()
