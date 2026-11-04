"""Run release-shell validator on packaged FeatureStacks v3 Stage 2.5 tree."""

from __future__ import annotations

import json
from pathlib import Path

from ssri_model.release_shell.validator import validate_release_shell_dataset

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "outputs" / "rehearsal" / "featurestacks_v3_stage25"
OUT = ROOT / "outputs" / "rehearsal" / "featurestacks_v3_validation.json"


def main() -> int:
    if not WORK.exists():
        print(f"MISSING {WORK} — run package_featurestacks_v3.py first")
        return 1
    report = validate_release_shell_dataset(WORK)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    channel = next(c for c in report["checks"] if c["name"] == "channel_quality")
    mins = next(c for c in report["checks"] if c["name"] == "hazard_minimums")
    print("overall", report["overall"], "can_train", report["can_train"])
    print("channel_quality", channel["status"], channel["message"][:240])
    print("hazard_minimums", mins["status"], mins["message"][:240])
    for h in report["hazards"]:
        print("hazard", h["hazard"], h["status"], h["labelled_tiles"], h["blocks_with_labels"])
    # Expectations
    ok_channels = channel["status"] == "FAIL" and all(
        name in channel["message"]
        for name in ("ndvi", "ndwi", "clay_mineral_ratio", "iron_oxide_index")
    )
    ok_mins = mins["status"] in {"WARN", "FAIL"} or any(
        h["status"] == "DISABLED" for h in report["hazards"]
    )
    print("EXPECT_all_sentinel_fail", ok_channels)
    print("EXPECT_below_minimum_flagged", ok_mins)
    print("wrote", OUT)
    return 0 if ok_channels and ok_mins else 1


if __name__ == "__main__":
    raise SystemExit(main())
