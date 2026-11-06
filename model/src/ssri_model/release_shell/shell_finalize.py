"""Finalize release-shell checkpoint metadata after multi-seed train/eval."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ssri_model.ml.labels import label_class_names
from ssri_model.release_shell.gates import STATUS_EVALUATED, aggregate_seed_gates
from ssri_model.release_shell.meta import build_training_region, embed_in_checkpoint
from ssri_model.release_shell.spatial_split import block5
from ssri_model.release_shell.validator import validate_release_shell_dataset


def collect_tiles_geo(dataset_root: Path) -> list[dict[str, Any]]:
    tiles: list[dict[str, Any]] = []
    for split in ("train", "validation", "test"):
        d = dataset_root / split
        if not d.is_dir():
            continue
        for sdir in d.iterdir():
            if not sdir.is_dir():
                continue
            meta_path = sdir / "metadata.json"
            if not meta_path.exists():
                continue
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            lat = meta.get("centroid_lat", meta.get("lat"))
            lon = meta.get("centroid_lon", meta.get("lon"))
            if lat is None or lon is None:
                continue
            tiles.append(
                {
                    "lat": float(lat),
                    "lon": float(lon),
                    "block": meta.get("block") or block5(float(lat), float(lon)),
                    "sample_id": sdir.name,
                }
            )
    return tiles


def build_shell_meta(
    *,
    dataset_root: Path,
    validation_report: dict[str, Any] | None,
    per_seed_evals: dict[str, dict[str, Any]],
    seeds: list[int],
    primary_seed: int,
) -> dict[str, Any]:
    validation_report = validation_report or validate_release_shell_dataset(dataset_root)
    tiles = collect_tiles_geo(dataset_root)
    region = build_training_region(tiles)

    hazards_out: dict[str, Any] = {}
    for hrow in validation_report.get("hazards") or []:
        name = hrow["hazard"]
        disabled = hrow.get("status") == "DISABLED"
        seed_gates = []
        seed_details = {}
        for seed_s, ev in per_seed_evals.items():
            hz = (ev.get("hazards") or {}).get(name) or {}
            g = hz.get("gate_status") or "trained, no demonstrated skill beyond slope"
            seed_gates.append(g)
            seed_details[str(seed_s)] = {
                "gate_status": g,
                "roc_auc": hz.get("roc_auc"),
                "delta_auc_vs_slope": (hz.get("baselines") or {}).get("delta_auc_vs_slope"),
                "delta_auc_ci95": (hz.get("baselines") or {}).get("delta_auc_ci95"),
            }
        if disabled:
            final_gate = "insufficient labelled data"
        elif not seed_gates:
            final_gate = "trained, no demonstrated skill beyond slope"
        else:
            final_gate = aggregate_seed_gates(seed_gates, min_pass=2)

        # Positive labels: from validation labelled_tiles
        has_pos = int(hrow.get("labelled_tiles") or 0) > 0
        hazards_out[name] = {
            "disabled_at_validation": disabled,
            "status": hrow.get("status"),
            "reason": hrow.get("reason"),
            "has_positive_labels": has_pos,
            "gate_status": final_gate,
            "seed_gates": seed_gates,
            "per_seed": seed_details,
            "seeds_passed": sum(1 for g in seed_gates if g == STATUS_EVALUATED),
        }

    # Ensure all three hazards present
    for name in label_class_names():
        hazards_out.setdefault(
            name,
            {
                "disabled_at_validation": True,
                "has_positive_labels": False,
                "gate_status": "insufficient labelled data",
                "reason": "Hazard missing from validation report.",
                "per_seed": {},
                "seed_gates": [],
                "seeds_passed": 0,
            },
        )

    from ssri_model.release_shell.channel_schema import SCHEMA_V1, schema_for_version
    from ssri_model.release_shell.spatial_split import LOCAL_EVIDENCE_LIMITATION, is_local_block_size

    manifest_path = Path(dataset_root) / "manifest.json"
    channel_schema_version = SCHEMA_V1
    channel_names = None
    local_evidence_only = False
    block_size_deg = 5.0
    if manifest_path.exists():
        try:
            man = json.loads(manifest_path.read_text(encoding="utf-8"))
            channel_schema_version = str(
                man.get("channel_schema_version")
                or (man.get("channel_schema") or {}).get("version")
                or SCHEMA_V1
            )
            channel_names = man.get("channel_names") or (man.get("channel_schema") or {}).get(
                "channel_names"
            )
            block_size_deg = float(
                man.get("block_size_deg")
                or (man.get("spatial_split") or {}).get("block_size_deg")
                or 5.0
            )
            local_evidence_only = bool(
                man.get("local_evidence_only")
                or (man.get("spatial_split") or {}).get("local_evidence_only")
                or is_local_block_size(block_size_deg)
            )
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    schema = (
        schema_for_version(channel_schema_version)
        if not channel_names
        else schema_for_version(channel_schema_version)
    )
    if channel_names:
        from ssri_model.release_shell.channel_schema import ChannelSchema

        schema = ChannelSchema(channel_schema_version, tuple(str(n) for n in channel_names))

    limitations = [
        "trained only on the uploaded data's geography; not validated elsewhere",
        "scientific status remains NOT_VALIDATED; not independently reviewed",
    ]
    if local_evidence_only:
        limitations.insert(0, LOCAL_EVIDENCE_LIMITATION)

    return {
        "schema": "ssri_release_shell_meta_v1",
        "seeds": seeds,
        "primary_seed": primary_seed,
        "training_region": region,
        "hazards": hazards_out,
        "scientific_validation_status": "NOT_VALIDATED",
        "score_framing": "relative susceptibility rankings",
        "data_hash": None,
        "channel_schema_version": schema.version,
        "channel_names": list(schema.channel_names),
        "block_size_deg": block_size_deg,
        "local_evidence_only": local_evidence_only,
        "limitations": limitations,
    }


def finalize_checkpoint(
    checkpoint_path: Path | str,
    *,
    dataset_root: Path,
    validation_report: dict[str, Any] | None,
    per_seed_evals: dict[str, dict[str, Any]],
    seeds: list[int],
    primary_seed: int,
    data_hash: str | None = None,
) -> dict[str, Any]:
    meta = build_shell_meta(
        dataset_root=Path(dataset_root),
        validation_report=validation_report,
        per_seed_evals=per_seed_evals,
        seeds=seeds,
        primary_seed=primary_seed,
    )
    if data_hash:
        meta["data_hash"] = data_hash
    embed_in_checkpoint(checkpoint_path, meta)
    return meta
