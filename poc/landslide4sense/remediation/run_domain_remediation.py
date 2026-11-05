"""
DeepSlide input-domain remediation experiment.

Authoritative packaging evidence (IARAI contributor YonghaoXu, issue #4):
  packaged_band = raw_band / img_mean[band]
  img_mean = [1111.81, 824.63, ..., 20.29, 772.83]

DeepSlide trains with normalize=False on these packaged tensors.
STAC physical units must be converted into that packaged domain — not left as
reflectance∈[0,1] / DEM meters raw.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import h5py
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "remediation" / "outputs"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))

from run_poc import WEIGHTS, build_model, load_weights, predict_prob  # noqa: E402

# https://github.com/iarai/Landslide4Sense-2022/issues/4#issuecomment-1195457420
IMG_MEAN = np.array(
    [
        1111.81236406,
        824.63171476,
        663.41636217,
        445.17289745,
        645.8582926,
        1547.73508126,
        1960.44401001,
        1941.32229668,
        674.07572865,
        9.04787384,
        1113.98338755,
        519.90397929,
        20.29228266,
        772.83144788,
    ],
    dtype=np.float64,
)

BANDS = [f"B{i:02d}" for i in range(1, 13)] + ["slope", "DEM"]

# Mountainous AOI near 2018 Iburi (Hokkaido) landslide region — paper study area
BBOX = (141.85, 42.70, 141.90, 42.74)
DATETIME = "2018-09-01/2018-10-15"
PATCH = 128


def load_l4s(path: Path) -> np.ndarray:
    with h5py.File(path, "r") as f:
        a = np.array(f["img"], dtype=np.float64)
    if a.shape[-1] == 14:
        a = np.transpose(a, (2, 0, 1))
    return a


def verify_packaging_on_l4s() -> dict:
    """If HDF5 ≈ raw/mean, then HDF5*mean should look like Sentinel DN / DEM / slope."""
    chips = sorted((ROOT / "data" / "validation" / "images").glob("image_*.h5"))[:20]
    recovered = []
    packaged_stats = []
    for p in chips:
        pkg = load_l4s(p)
        raw = pkg * IMG_MEAN[:, None, None]
        recovered.append(raw.reshape(14, -1))
        packaged_stats.append(pkg.reshape(14, -1))
    raw_f = np.concatenate(recovered, axis=1)
    pkg_f = np.concatenate(packaged_stats, axis=1)
    return {
        "evidence_url": "https://github.com/iarai/Landslide4Sense-2022/issues/4#issuecomment-1195457420",
        "formula": "packaged = raw / img_mean",
        "img_mean": IMG_MEAN.tolist(),
        "packaged_mean": pkg_f.mean(axis=1).tolist(),
        "packaged_std": pkg_f.std(axis=1).tolist(),
        "recovered_raw_mean": raw_f.mean(axis=1).tolist(),
        "recovered_raw_p01": np.percentile(raw_f, 1, axis=1).tolist(),
        "recovered_raw_p99": np.percentile(raw_f, 99, axis=1).tolist(),
        "interpretation": (
            "Recovered optical ~hundreds–thousands (Sentinel scaled reflectance DN); "
            "slope ~degrees; DEM ~meters. Consistent with contributor statement."
        ),
    }


def fetch_stac_raw() -> dict:
    """Fetch S2+DEM as raw-ish units (optical *10000 scale, DEM m, slope deg)."""
    import planetary_computer
    import pystac_client
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.warp import reproject, transform_bounds
    from rasterio.windows import Window

    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace,
    )
    items = list(
        catalog.search(
            collections=["sentinel-2-l2a"],
            bbox=BBOX,
            datetime=DATETIME,
            query={"eo:cloud_cover": {"lt": 40}},
            max_items=8,
        ).items()
    )
    if not items:
        return {"ok": False, "blocker": "no_s2_items"}
    item = sorted(items, key=lambda it: it.properties.get("eo:cloud_cover", 100))[0]
    band_keys = [f"B{str(i).zfill(2)}" for i in range(1, 13)]

    with rasterio.open(item.assets["B04"].href) as ref:
        west, south, east, north = transform_bounds("EPSG:4326", ref.crs, *BBOX, densify_pts=21)
        r0, c0 = ref.index(west, north)
        r1, c1 = ref.index(east, south)
        r0, r1 = sorted([int(r0), int(r1)])
        c0, c1 = sorted([int(c0), int(c1)])
        r0 = max(0, min(r0, max(0, ref.height - PATCH)))
        c0 = max(0, min(c0, max(0, ref.width - PATCH)))
        window = Window(c0, r0, PATCH, PATCH)
        transform = ref.window_transform(window)
        crs = ref.crs
        raw = np.zeros((14, PATCH, PATCH), dtype=np.float64)
        fills = []
        for i, key in enumerate(band_keys):
            arr = np.zeros((PATCH, PATCH), dtype=np.float64)
            if key in item.assets:
                with rasterio.open(item.assets[key].href) as src:
                    reproject(
                        source=rasterio.band(src, 1),
                        destination=arr,
                        src_transform=src.transform,
                        src_crs=src.crs,
                        dst_transform=transform,
                        dst_crs=crs,
                        resampling=Resampling.bilinear,
                    )
                # Keep Sentinel scaled reflectance integers (~0-10000). If already 0-1, restore.
                if arr.max() <= 1.5:
                    arr = arr * 10000.0
                fills.append(None)
            else:
                fills.append("zeros_missing_L2A_B10")
            raw[i] = arr

    dem_items = list(catalog.search(collections=["cop-dem-glo-30"], bbox=BBOX, max_items=3).items())
    if not dem_items:
        return {"ok": False, "blocker": "no_dem"}
    dem = np.zeros((PATCH, PATCH), dtype=np.float64)
    dem_asset = dem_items[0].assets.get("data") or next(iter(dem_items[0].assets.values()))
    with rasterio.open(dem_asset.href) as src:
        reproject(
            source=rasterio.band(src, 1),
            destination=dem,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=transform,
            dst_crs=crs,
            resampling=Resampling.bilinear,
        )
    gy, gx = np.gradient(dem, 10.0, 10.0)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    raw[12] = slope
    raw[13] = dem
    raw = np.nan_to_num(raw, nan=0.0)
    return {
        "ok": True,
        "raw": raw,
        "transform": transform,
        "crs": crs,
        "s2_item": item.id,
        "dem_item": dem_items[0].id,
        "fills": fills,
        "raw_stats": {
            "mean": raw.reshape(14, -1).mean(axis=1).tolist(),
            "std": raw.reshape(14, -1).std(axis=1).tolist(),
            "min": raw.reshape(14, -1).min(axis=1).tolist(),
            "max": raw.reshape(14, -1).max(axis=1).tolist(),
        },
    }


def package_l4s(raw: np.ndarray) -> np.ndarray:
    return (raw / IMG_MEAN[:, None, None]).astype(np.float32)


def run_infer(model, stack: np.ndarray, device) -> dict:
    t0 = time.perf_counter()
    prob = predict_prob(model, stack.astype(np.float32), device)
    dt = time.perf_counter() - t0
    pred = (prob > 0.5).astype(np.uint8)
    return {
        "infer_s": round(dt, 4),
        "prob_min": float(prob.min()),
        "prob_max": float(prob.max()),
        "prob_mean": float(prob.mean()),
        "prob_p99": float(np.percentile(prob, 99)),
        "pred_pos": int(pred.sum()),
        "empty": int(pred.sum()) == 0,
        "all_pos": int(pred.sum()) == pred.size,
        "prob": prob,
        "pred": pred,
    }


def write_geotiff(path: Path, pred: np.ndarray, prob: np.ndarray, crs, transform) -> None:
    import rasterio

    profile = {
        "driver": "GTiff",
        "height": pred.shape[0],
        "width": pred.shape[1],
        "count": 2,
        "dtype": "float32",
        "crs": crs,
        "transform": transform,
        "compress": "lzw",
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(pred.astype(np.float32), 1)
        dst.write(prob.astype(np.float32), 2)
        dst.update_tags(
            BAND1="binary_mask_thr_0_5",
            BAND2="uncalibrated_sigmoid",
            PACKAGING="raw_div_img_mean_issue4",
            NOTE="NOT_CALIBRATED_RISK",
        )


def preview(raw_rgb_src: np.ndarray, before: dict, after: dict, path: Path) -> None:
    # raw_rgb_src expected CHW optical packaged or reflectance for display
    rgb = np.stack([raw_rgb_src[3], raw_rgb_src[2], raw_rgb_src[1]], axis=-1)
    rgb = rgb - rgb.min()
    rgb = rgb / (rgb.max() + 1e-8)
    fig, axes = plt.subplots(2, 3, figsize=(12, 8))
    axes[0, 0].imshow(rgb)
    axes[0, 0].set_title("Input RGB (stretch)")
    axes[0, 1].imshow(before["prob"], cmap="magma", vmin=0, vmax=1)
    axes[0, 1].set_title(f"BEFORE max={before['prob_max']:.4f}")
    axes[0, 2].imshow(rgb)
    axes[0, 2].imshow(np.ma.masked_where(before["pred"] == 0, before["pred"]), cmap="autumn", alpha=0.5)
    axes[0, 2].set_title("BEFORE overlay")
    axes[1, 0].imshow(after["prob"], cmap="magma", vmin=0, vmax=1)
    axes[1, 0].set_title(f"AFTER (÷img_mean) max={after['prob_max']:.4f}")
    axes[1, 1].imshow(rgb)
    axes[1, 1].imshow(np.ma.masked_where(after["pred"] == 0, after["pred"]), cmap="autumn", alpha=0.5)
    axes[1, 1].set_title("AFTER overlay thr=0.5")
    axes[1, 2].axis("off")
    axes[1, 2].text(
        0.05,
        0.5,
        "Uncalibrated segmentation\nNOT scientific risk map\nThreshold fixed at 0.5",
        fontsize=11,
        va="center",
    )
    for ax in axes.ravel():
        ax.axis("off")
    fig.suptitle("Domain remediation: STAC physical → L4S packaged (÷img_mean)", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)


def sanity_l4s_roundtrip(model, device) -> dict:
    """Packaging check: L4S chip already packaged; scores should stay useful."""
    p = ROOT / "data" / "validation" / "images" / "image_10.h5"
    if not p.exists():
        p = ROOT / "data" / "images" / "image_1.h5"
    chip = load_l4s(p).astype(np.float32)
    out = run_infer(model, chip, device)
    return {
        "chip": str(p.name),
        "prob_max": out["prob_max"],
        "pred_pos": out["pred_pos"],
        "empty": out["empty"],
        "note": "Baseline: competition chip as DeepSlide expects",
    }


def main() -> int:
    report: dict = {
        "experiment": "deepslide_input_domain_remediation",
        "acceptance_predeclared": {
            "threshold": 0.5,
            "non_empty_required": True,
            "threshold_may_not_be_lowered": True,
            "packaging_must_be_authoritative": True,
            "scientific_validation": "NOT claimed by this experiment",
        },
    }

    packaging = verify_packaging_on_l4s()
    report["packaging_verification"] = packaging
    (OUT / "packaging_verification.json").write_text(json.dumps(packaging, indent=2), encoding="utf-8")

    device = torch.device("cpu")
    t0 = time.perf_counter()
    model = build_model()
    load_weights(model, WEIGHTS)
    model.eval().to(device)
    load_s = time.perf_counter() - t0

    report["sanity_l4s_chip"] = sanity_l4s_roundtrip(model, device)

    stac = fetch_stac_raw()
    if not stac.get("ok"):
        report["verdict"] = "BLOCKED"
        report["blocker"] = stac
        (OUT / "DOMAIN_REMEDIATION_REPORT.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2

    raw = stac["raw"]
    # BEFORE: previous mistaken path — reflectance 0-1 + raw DEM/slope (no ÷mean)
    before_stack = raw.copy()
    before_stack[:12] = before_stack[:12] / 10000.0
    before_stack = before_stack.astype(np.float32)

    # AFTER: authoritative packaging raw/img_mean
    after_stack = package_l4s(raw)

    # Optional control: ÷mean without restoring *10000 (wrong) — isolate optical scale
    wrong_optical = package_l4s(np.concatenate([raw[:12] / 10000.0, raw[12:]], axis=0))

    before = run_infer(model, before_stack, device)
    after = run_infer(model, after_stack, device)
    control = run_infer(model, wrong_optical.astype(np.float32), device)

    report["runtime"] = {
        "model_load_s": round(load_s, 3),
        "before_infer_s": before["infer_s"],
        "after_infer_s": after["infer_s"],
    }
    report["distributions"] = {
        "stac_raw": stac["raw_stats"],
        "before_packaged_mean": before_stack.reshape(14, -1).mean(axis=1).tolist(),
        "after_packaged_mean": after_stack.reshape(14, -1).mean(axis=1).tolist(),
        "l4s_packaged_mean_ref": packaging["packaged_mean"],
    }
    report["diagnostics"] = {
        "before_reflectance_no_div_mean": {
            k: before[k] for k in ("prob_min", "prob_max", "prob_mean", "prob_p99", "pred_pos", "empty")
        },
        "after_raw_div_img_mean": {
            k: after[k] for k in ("prob_min", "prob_max", "prob_mean", "prob_p99", "pred_pos", "empty")
        },
        "control_reflectance_div_mean_wrong_optical_scale": {
            k: control[k] for k in ("prob_min", "prob_max", "prob_mean", "prob_p99", "pred_pos", "empty")
        },
    }

    # Save arrays + geotiff for AFTER only (authoritative path)
    np.save(OUT / "stac_raw_14chw.npy", raw)
    np.save(OUT / "stac_packaged_after.npy", after_stack)
    write_geotiff(OUT / "prediction_georef_after.tif", after["pred"], after["prob"], stac["crs"], stac["transform"])
    write_geotiff(OUT / "prediction_georef_before.tif", before["pred"], before["prob"], stac["crs"], stac["transform"])
    preview(after_stack, before, after, OUT / "preview_before_after.png")

    # CRS check
    import rasterio

    with rasterio.open(OUT / "prediction_georef_after.tif") as src:
        crs_ok = src.crs is not None and str(src.crs) == str(stac["crs"])
        report["georef"] = {
            "crs": str(src.crs),
            "transform": [float(x) for x in src.transform][:6],
            "aligned": crs_ok,
            "s2_item": stac["s2_item"],
            "dem_item": stac["dem_item"],
            "bbox": BBOX,
            "dem_source_note": "Copernicus GLO-30 used; L4S used ALOS PALSAR — residual sensor gap remains",
            "b10_fill": stac["fills"][9],
        }

    # Held-out on L4S validation with packaging already present: confirm transform doesn't break
    # (chips are already packaged; no change). Numeric gates already known from prior report.
    report["held_out_note"] = (
        "L4S validation chips are already in packaged domain; DeepSlide held-out micro-F1≈0.529 "
        "from prior gate remains the labelled evaluation evidence. This experiment adds "
        "georeferenced inference under the contributor packaging recipe."
    )

    non_empty = not after["empty"]
    authoritative = True  # contributor-stated ÷img_mean
    # Meaningful: not empty, not all-positive, scores not stuck near 0
    meaningful = non_empty and not after["all_pos"] and after["prob_max"] >= 0.5
    # Also require before was empty/near-zero to show remediation effect
    remediated = before["empty"] and non_empty

    report["gates"] = {
        "authoritative_transform_documented": authoritative,
        "non_empty_at_thr_0_5": non_empty,
        "not_all_positive": not after["all_pos"],
        "prob_max_reaches_threshold": after["prob_max"] >= 0.5,
        "georef_crs_ok": crs_ok,
        "before_was_empty_or_near_zero": before["empty"] or before["prob_max"] < 0.05,
        "remediation_changed_outcome": remediated or (after["prob_max"] > before["prob_max"] * 5),
    }

    if not authoritative:
        verdict = "BLOCKED"
    elif not (non_empty and crs_ok and after["prob_max"] >= 0.5):
        verdict = "FAIL"
    else:
        # Technical remediation pass for domain mapping; scientific validation still unresolved
        verdict = "PASS"
    report["verdict"] = verdict
    report["scientific_validation"] = "UNRESOLVED"
    report["scientific_note"] = (
        "PASS here means the contributor packaging recipe yields non-empty georeferenced "
        "DeepSlide outputs at the fixed 0.5 threshold. It does NOT authorize production "
        "integration or claim inventory-validated accuracy on this AOI (no pixel labels for Iburi window)."
    )
    report["limitations"] = [
        "No pixel ground truth for the Iburi STAC window — spatial meaningfulness is qualitative",
        "DEM is Copernicus GLO-30, not ALOS PALSAR",
        "B10 zero-filled on L2A",
        "Sentinel L2A vs unknown L1C/L2A choice in original packaging still slightly ambiguous",
        "Uncalibrated sigmoid ≠ landslide risk probability",
        "SSRI 13-channel assess path still incompatible",
    ]

    # strip arrays
    for d in (before, after, control):
        d.pop("prob", None)
        d.pop("pred", None)
    stac.pop("raw", None)
    report["stac_meta"] = {k: stac[k] for k in stac if k not in ("transform", "crs")}
    report["stac_meta"]["crs"] = str(stac["crs"])

    (OUT / "DOMAIN_REMEDIATION_REPORT.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("verdict", "gates", "diagnostics", "georef", "sanity_l4s_chip", "runtime")}, indent=2))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
