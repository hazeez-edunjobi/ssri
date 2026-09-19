"""CLI entry point for SSRI offline inference."""

from __future__ import annotations

import argparse
import sys

from ssri_model.inference import InferenceConfig, run_inference
from ssri_model.inference.exceptions import InferenceError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run SSRI geospatial hazard inference from a trained checkpoint.",
    )
    parser.add_argument("--checkpoint", required=True, help="Path to best.pt checkpoint")
    parser.add_argument("--features", required=True, help="Path to feature_stack.npy")
    parser.add_argument("--manifest", required=True, help="Path to manifest.json")
    parser.add_argument("--statistics", required=True, help="Path to statistics.json")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--tile-size", type=int, default=512, help="Inference tile size")
    parser.add_argument("--overlap", type=int, default=64, help="Tile overlap in pixels")
    parser.add_argument("--batch-size", type=int, default=4, help="Window batch size")
    parser.add_argument(
        "--device",
        default="auto",
        choices=("auto", "cpu", "cuda"),
        help="Inference device",
    )
    parser.add_argument(
        "--mixed-precision",
        action="store_true",
        help="Enable CUDA mixed precision (disabled on CPU)",
    )
    parser.add_argument(
        "--individual-probability-bands",
        action="store_true",
        help="Write per-class probability GeoTIFFs",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = InferenceConfig(
        checkpoint_path=args.checkpoint,
        feature_path=args.features,
        manifest_path=args.manifest,
        statistics_path=args.statistics,
        output_dir=args.output,
        tile_size=args.tile_size,
        overlap=args.overlap,
        batch_size=args.batch_size,
        device=args.device,
        mixed_precision=args.mixed_precision,
        save_individual_probability_bands=args.individual_probability_bands,
    )
    try:
        result = run_inference(config)
    except InferenceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote predictions to {result.prediction_path.parent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
