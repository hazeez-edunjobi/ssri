"""Train SSRIMultiTaskModel on USGS FeatureStack samples + source holdout eval.

Reads ``data/datasets/usgs_landslide_featurestacks/v1`` produced by
``build_usgs_feature_dataset``. Saves checkpoint ``models/ssri-foundation-v1.pt``
and an experiment manifest with measured (not fabricated) metrics.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch
from dotenv import load_dotenv
from torch.utils.data import DataLoader, Dataset

from ssri_model.architecture.config import SSRIModelConfig
from ssri_model.architecture.multitask import (
    SSRIMultiTaskModel,
    masked_multitask_bce_with_logits,
)
from ssri_model.evaluation.calibration_ece import expected_calibration_error
from ssri_model.training.seed import set_seed

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DATASET = REPO_ROOT / "data" / "datasets" / "usgs_landslide_featurestacks" / "v3"
DEFAULT_CHECKPOINT = REPO_ROOT / "models" / "ssri-foundation-v1.pt"
DEFAULT_EXPERIMENT_ROOT = REPO_ROOT / "experiments" / "foundation"


class MultitaskFeatureDataset(Dataset):
    """Load FeatureStacks + multitask masks for landslide-labelled tiles."""

    def __init__(
        self,
        dataset_root: Path,
        sample_ids: list[str],
        *,
        mean: np.ndarray,
        std: np.ndarray,
        target_hw: tuple[int, int] | None = None,
    ) -> None:
        self.dataset_root = dataset_root
        self.sample_ids = list(sample_ids)
        self.mean = mean.astype(np.float32).reshape(-1, 1, 1)
        self.std = np.maximum(std.astype(np.float32), 1e-6).reshape(-1, 1, 1)
        self.target_hw = target_hw
        self.samples_root = dataset_root / "samples"

    def __len__(self) -> int:
        return len(self.sample_ids)

    def __getitem__(self, index: int) -> dict[str, torch.Tensor]:
        sid = self.sample_ids[index]
        sample_dir = self.samples_root / sid
        features = np.load(sample_dir / "feature_stack.npy").astype(np.float32)
        labels = np.load(sample_dir / "labels_multitask.npz")

        # Replace non-finite with channel mean (pre-norm).
        for c in range(features.shape[0]):
            band = features[c]
            bad = ~np.isfinite(band)
            if bad.any():
                band = band.copy()
                band[bad] = float(self.mean[c, 0, 0])
                features[c] = band

        features = (features - self.mean) / self.std

        if self.target_hw is not None:
            features = _center_crop_or_pad(features, self.target_hw)

        out: dict[str, torch.Tensor] = {
            "features": torch.from_numpy(features),
            "sample_id": sid,  # type: ignore[dict-item]
        }
        for task in ("landslide", "subsidence", "liquefaction"):
            target = labels[task].astype(np.float32)
            mask = labels[f"{task}_mask"].astype(np.float32)
            if self.target_hw is not None:
                target = _center_crop_or_pad(target[None, ...], self.target_hw)[0]
                mask = _center_crop_or_pad(mask[None, ...], self.target_hw)[0]
            out[f"target_{task}"] = torch.from_numpy(target)
            out[f"mask_{task}"] = torch.from_numpy(mask)
        return out


def _center_crop_or_pad(arr: np.ndarray, hw: tuple[int, int]) -> np.ndarray:
    """Center-crop or zero-pad last two dims to ``hw``."""
    th, tw = hw
    if arr.ndim == 2:
        arr = arr[None, ...]
        squeeze = True
    else:
        squeeze = False
    c, h, w = arr.shape
    out = np.zeros((c, th, tw), dtype=arr.dtype)
    # Source window
    src_y0 = max(0, (h - th) // 2)
    src_x0 = max(0, (w - tw) // 2)
    src_y1 = min(h, src_y0 + th)
    src_x1 = min(w, src_x0 + tw)
    # Dest window
    dy = src_y1 - src_y0
    dx = src_x1 - src_x0
    dst_y0 = (th - dy) // 2
    dst_x0 = (tw - dx) // 2
    out[:, dst_y0 : dst_y0 + dy, dst_x0 : dst_x0 + dx] = arr[
        :, src_y0:src_y1, src_x0:src_x1
    ]
    return out[0] if squeeze else out


def _collate(batch: list[dict[str, Any]]) -> dict[str, Any]:
    keys = [k for k in batch[0] if k != "sample_id"]
    out: dict[str, Any] = {
        k: torch.stack([item[k] for item in batch], dim=0) for k in keys
    }
    out["sample_id"] = [item["sample_id"] for item in batch]
    return out


def _git_commit() -> str:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=REPO_ROOT,
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return "UNKNOWN"


def _roc_auc(y_true: np.ndarray, y_score: np.ndarray) -> float | None:
    """Trapezoidal ROC-AUC; None if only one class present."""
    y_true = y_true.astype(np.int32)
    if y_true.min() == y_true.max():
        return None
    order = np.argsort(-y_score)
    y_true = y_true[order]
    y_score = y_score[order]
    tps = np.cumsum(y_true)
    fps = np.cumsum(1 - y_true)
    tps = np.concatenate([[0], tps])
    fps = np.concatenate([[0], fps])
    tpr = tps / tps[-1]
    fpr = fps / fps[-1]
    return float(np.trapezoid(tpr, fpr))


def _pr_auc(y_true: np.ndarray, y_score: np.ndarray) -> float | None:
    y_true = y_true.astype(np.int32)
    if y_true.sum() == 0:
        return None
    order = np.argsort(-y_score)
    y_true = y_true[order]
    tps = np.cumsum(y_true)
    fps = np.cumsum(1 - y_true)
    precision = tps / np.maximum(tps + fps, 1)
    recall = tps / tps[-1]
    precision = np.concatenate([[1.0], precision])
    recall = np.concatenate([[0.0], recall])
    return float(np.trapezoid(precision, recall))


@torch.no_grad()
def evaluate_split(
    model: SSRIMultiTaskModel,
    loader: DataLoader,
    device: torch.device,
) -> dict[str, Any]:
    model.eval()
    # Tile-level scores: mean probability over pixels (landslide task).
    y_true: list[float] = []
    y_score: list[float] = []
    pixel_true: list[np.ndarray] = []
    pixel_prob: list[np.ndarray] = []

    for batch in loader:
        features = batch["features"].to(device)
        logits = model(features)
        prob = torch.sigmoid(logits["landslide"]).cpu().numpy()
        target = batch["target_landslide"].numpy()
        mask = batch["mask_landslide"].numpy() > 0.5
        for i in range(prob.shape[0]):
            m = mask[i]
            if not m.any():
                continue
            p = prob[i][m]
            t = target[i][m]
            # Tile label = mode of labelled pixels (constant by construction).
            tile_label = float(t.mean() > 0.5)
            tile_score = float(p.mean())
            y_true.append(tile_label)
            y_score.append(tile_score)
            pixel_true.append(t.astype(np.float32))
            pixel_prob.append(p.astype(np.float32))

    y_true_a = np.asarray(y_true, dtype=np.float32)
    y_score_a = np.asarray(y_score, dtype=np.float32)
    metrics: dict[str, Any] = {
        "n_tiles": int(len(y_true)),
        "positive_tiles": int(y_true_a.sum()) if len(y_true_a) else 0,
        "negative_tiles": int((1 - y_true_a).sum()) if len(y_true_a) else 0,
        "tile_roc_auc": _roc_auc(y_true_a, y_score_a) if len(y_true_a) else None,
        "tile_pr_auc": _pr_auc(y_true_a, y_score_a) if len(y_true_a) else None,
    }

    if pixel_true:
        pt = np.concatenate(pixel_true)
        pp = np.concatenate(pixel_prob)
        metrics["pixel_roc_auc"] = _roc_auc(pt, pp)
        metrics["pixel_pr_auc"] = _pr_auc(pt, pp)
        # Binary metrics at 0.5
        pred = (pp >= 0.5).astype(np.int32)
        truth = pt.astype(np.int32)
        tp = int(((pred == 1) & (truth == 1)).sum())
        fp = int(((pred == 1) & (truth == 0)).sum())
        fn = int(((pred == 0) & (truth == 1)).sum())
        tn = int(((pred == 0) & (truth == 0)).sum())
        precision = tp / max(tp + fp, 1)
        recall = tp / max(tp + fn, 1)
        f1 = 2 * precision * recall / max(precision + recall, 1e-12)
        metrics["pixel_precision"] = precision
        metrics["pixel_recall"] = recall
        metrics["pixel_f1"] = f1
        metrics["confusion_matrix"] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
        }
        # Brier score on pixels and tiles
        metrics["pixel_brier"] = float(np.mean((pp - pt) ** 2))
        metrics["tile_brier"] = float(np.mean((y_score_a - y_true_a) ** 2)) if len(y_true_a) else None
        try:
            cal = expected_calibration_error(pp, truth, n_bins=10)
            metrics["ece"] = float(cal.ece)
        except Exception as exc:  # noqa: BLE001
            metrics["ece"] = None
            metrics["ece_error"] = str(exc)
    return metrics


def train(args: argparse.Namespace) -> dict[str, Any]:
    load_dotenv(REPO_ROOT / ".env")
    set_seed(args.seed)

    dataset_root = Path(args.dataset)
    manifest = json.loads((dataset_root / "manifest.json").read_text(encoding="utf-8"))
    stats = json.loads((dataset_root / "statistics.json").read_text(encoding="utf-8"))
    mean = np.asarray(stats["mean"], dtype=np.float32)
    std = np.asarray(stats["std"], dtype=np.float32)

    splits = manifest["splits"]
    for name in ("train", "validation", "test"):
        if not splits.get(name):
            raise RuntimeError(f"Dataset split '{name}' is empty — cannot train/evaluate")

    # Determine common spatial size from first train sample.
    first = next(
        (dataset_root / "samples" / sid / "feature_stack.npy")
        for sid in splits["train"]
        if (dataset_root / "samples" / sid / "feature_stack.npy").exists()
    )
    probe = np.load(first)
    # Use median-ish fixed size: 64x64 crop/pad for batching.
    target_hw = (args.spatial_size, args.spatial_size)

    train_ds = MultitaskFeatureDataset(
        dataset_root, splits["train"], mean=mean, std=std, target_hw=target_hw
    )
    val_ds = MultitaskFeatureDataset(
        dataset_root, splits["validation"], mean=mean, std=std, target_hw=target_hw
    )
    test_ds = MultitaskFeatureDataset(
        dataset_root, splits["test"], mean=mean, std=std, target_hw=target_hw
    )

    train_loader = DataLoader(
        train_ds,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=0,
        collate_fn=_collate,
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=0,
        collate_fn=_collate,
    )
    test_loader = DataLoader(
        test_ds,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=0,
        collate_fn=_collate,
    )

    device = torch.device(
        args.device
        if args.device != "auto"
        else ("cuda" if torch.cuda.is_available() else "cpu")
    )
    model = SSRIMultiTaskModel(SSRIModelConfig(), dann=False).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=args.lr, weight_decay=args.weight_decay
    )

    experiment_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    exp_dir = Path(args.experiment_root) / experiment_id
    exp_dir.mkdir(parents=True, exist_ok=True)

    history: list[dict[str, Any]] = []
    best_val_auc = -1.0
    best_state: dict[str, Any] | None = None
    best_epoch = 0
    t_start = time.perf_counter()

    for epoch in range(1, args.epochs + 1):
        model.train()
        losses: list[float] = []
        for batch in train_loader:
            features = batch["features"].to(device)
            logits = model(features)
            targets = {
                t: batch[f"target_{t}"].to(device)
                for t in ("landslide", "subsidence", "liquefaction")
            }
            masks = {
                t: batch[f"mask_{t}"].to(device)
                for t in ("landslide", "subsidence", "liquefaction")
            }
            pixel_loss = masked_multitask_bce_with_logits(logits, targets, masks)
            # Presence/absence is a tile-level decision; add mean-logit BCE so the
            # network is not only fit to spatially constant pixel maps.
            tile_logit = logits["landslide"].mean(dim=(1, 2))
            tile_target = targets["landslide"].mean(dim=(1, 2)).clamp(0.0, 1.0)
            tile_loss = torch.nn.functional.binary_cross_entropy_with_logits(
                tile_logit, tile_target
            )
            loss = pixel_loss + tile_loss
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
            losses.append(float(loss.item()))

        val_metrics = evaluate_split(model, val_loader, device)
        train_loss = float(np.mean(losses)) if losses else float("nan")
        record = {
            "epoch": epoch,
            "train_loss": train_loss,
            "val": val_metrics,
        }
        history.append(record)
        val_auc = val_metrics.get("tile_roc_auc")
        logger.info(
            "epoch %s train_loss=%.4f val_tile_auc=%s",
            epoch,
            train_loss,
            val_auc,
        )
        score = float(val_auc) if val_auc is not None else -train_loss
        if score > best_val_auc:
            best_val_auc = score
            best_epoch = epoch
            best_state = {
                k: v.detach().cpu().clone() for k, v in model.state_dict().items()
            }

    assert best_state is not None
    model.load_state_dict(best_state)

    test_metrics = evaluate_split(model, test_loader, device)
    val_metrics = evaluate_split(model, val_loader, device)
    duration_s = time.perf_counter() - t_start

    checkpoint_path = Path(args.checkpoint)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model_name": "SSRIMultiTaskModel",
        "version": "ssri-foundation-v1",
        "state_dict": best_state,
        "config": SSRIModelConfig().__dict__,
        "dataset": {
            "path": str(dataset_root),
            "version": manifest.get("version"),
            "n_built": manifest.get("n_built"),
            "splits": {k: len(v) for k, v in splits.items()},
        },
        "normalization": {"mean": mean.tolist(), "std": std.tolist()},
        "spatial_size": args.spatial_size,
        "seed": args.seed,
        "best_epoch": best_epoch,
        "git_commit": _git_commit(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    torch.save(payload, checkpoint_path)

    experiment = {
        "experiment_id": experiment_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "dataset": str(dataset_root),
        "dataset_manifest_summary": {
            "n_built": manifest.get("n_built"),
            "n_failed": manifest.get("n_failed"),
            "split_strategy": manifest.get("split_strategy"),
            "splits": {k: len(v) for k, v in splits.items()},
        },
        "hyperparameters": {
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "lr": args.lr,
            "weight_decay": args.weight_decay,
            "spatial_size": args.spatial_size,
            "seed": args.seed,
            "device": str(device),
        },
        "hardware": {
            "device": str(device),
            "cuda_available": torch.cuda.is_available(),
            "cuda_name": torch.cuda.get_device_name(0)
            if torch.cuda.is_available()
            else None,
        },
        "training_duration_s": duration_s,
        "best_epoch": best_epoch,
        "best_val_tile_roc_auc": best_val_auc if best_val_auc >= 0 else None,
        "validation_metrics": val_metrics,
        "test_metrics": test_metrics,
        "source_auc_gate_target": 0.88,
        "source_auc_gate_passed": (
            test_metrics.get("tile_roc_auc") is not None
            and float(test_metrics["tile_roc_auc"]) >= 0.88
        ),
        "checkpoint": str(checkpoint_path),
        "history": history,
        "notes": [
            "Landslide-only supervision from USGS inventory + documented pseudo-absences.",
            "Subsidence/liquefaction heads untrained (masks all zero).",
            "Gravity is WGM2012 CONUS clip, not EIGEN-6C4.",
            "Metrics are measured on this run; do not treat as PRD-complete science.",
        ],
    }
    (exp_dir / "experiment.json").write_text(
        json.dumps(experiment, indent=2),
        encoding="utf-8",
    )
    (exp_dir / "history.json").write_text(
        json.dumps(history, indent=2),
        encoding="utf-8",
    )
    logger.info("Wrote checkpoint %s", checkpoint_path)
    logger.info("Test tile ROC-AUC=%s", test_metrics.get("tile_roc_auc"))
    return experiment


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    p.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    p.add_argument("--experiment-root", type=Path, default=DEFAULT_EXPERIMENT_ROOT)
    p.add_argument("--epochs", type=int, default=30)
    p.add_argument("--batch-size", type=int, default=4)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--weight-decay", type=float, default=1e-4)
    p.add_argument("--spatial-size", type=int, default=64)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--device", default="auto")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    train(args)


if __name__ == "__main__":
    main()
