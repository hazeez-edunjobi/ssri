# Reproduce Gate A build + evaluation

Requires: Poetry env under `model/` with DeepSlide deps already used by the PoC (`torch`, `segmentation_models_pytorch`, `rasterio`, `pystac-client`, `planetary-computer`, `numpy`). No paid APIs or cloud GPU.

From repo root:

```powershell
poetry -C model run python ../poc/landslide4sense/production_gates/gate_a_build/build_and_eval.py
```

Optional inventory probe:

```powershell
poetry -C model run python ../poc/landslide4sense/production_gates/gate_a_build/probe_inventory.py
```

(Run probes from repo root so relative catalog paths resolve, or edit the script to use absolute paths.)

## Outputs

| Artifact | Path |
|----------|------|
| Predeclared acceptance | `acceptance.json` |
| Selected sites / blocks | `outputs/selected_sites.json` |
| Per-chip stacks, labels, predictions | `outputs/chips/<id>/` |
| Chip metadata | `outputs/chip_records.json` |
| Full eval report | `outputs/gate_a_eval_report.json` |
| Run log | `outputs/run_log.txt` |

## Fixed contract (do not change for this gate)

- Checkpoint: `poc/landslide4sense/weights/mobilenetv2.pth`
- Packaging: `l4s-pack-v1-div-img-mean` via `DeepSlideEngine` / `package_raw_stack`
- Threshold: **0.5**
- Production `/api/v1/assess`: untouched
