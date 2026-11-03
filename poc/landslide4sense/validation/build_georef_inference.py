"""
Build a 14-band georeferenced window from free Planetary Computer STAC
(Sentinel-2 L2A + Copernicus DEM), run DeepSlide inference, write GeoTIFF.

IMPORTANT domain note:
Landslide4Sense competition HDF5 values are pre-scaled competition tensors
(observed range ~0–6+), not raw Sentinel reflectance / DEM meters.
DeepSlide was trained on those tensors with normalize=False.
A STAC-built stack in native physical units is band-order-compatible but
NOT distribution-matched unless the unpublished competition scaling is
reproduced. This script documents that gap and still produces a real-CRS
output so Phase 2/4 can be judged honestly.
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "validation" / "outputs" / "georef"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))

from run_poc import WEIGHTS, build_model, load_weights, predict_prob  # noqa: E402

# Small AOI near a documented landslide-prone region (Hiroshima, Japan vicinity)
# Used only to exercise CRS-preserving ingest — not a labelled validation site.
BBOX = (132.45, 34.40, 132.47, 34.42)  # west, south, east, north
DATETIME = "2018-06-01/2018-08-31"
PATCH = 128


def install_hint(exc: Exception) -> dict:
    return {
        "ok": False,
        "blocker": "missing_dependency",
        "error": str(exc),
        "remediation": "poetry -C model run pip install pystac-client planetary-computer",
    }


def fetch_stack() -> dict:
    try:
        import planetary_computer
        import pystac_client
        import rasterio
        from rasterio.enums import Resampling
        from rasterio.windows import Window
        from rasterio.warp import reproject, transform_bounds
    except Exception as exc:  # noqa: BLE001
        return install_hint(exc)

    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace,
    )
    search = catalog.search(
        collections=["sentinel-2-l2a"],
        bbox=BBOX,
        datetime=DATETIME,
        query={"eo:cloud_cover": {"lt": 20}},
        max_items=5,
    )
    items = list(search.items())
    if not items:
        return {"ok": False, "blocker": "no_sentinel_items", "bbox": BBOX, "datetime": DATETIME}

    item = sorted(items, key=lambda it: it.properties.get("eo:cloud_cover", 100))[0]
    # S2 band asset keys on PC
    band_keys = [f"B{str(i).zfill(2)}" for i in range(1, 13)]
    # L2A products typically omit B10 (cirrus); L4S still expects a 12th optical slot.
    # Documented fill: zeros for missing B10 only.
    required = [k for k in band_keys if k != "B10"]
    missing = [k for k in required if k not in item.assets]
    if missing:
        return {"ok": False, "blocker": "missing_s2_assets", "missing": missing, "item": item.id}
    b10_filled = "B10" not in item.assets

    # Use B04 (10 m) as reference grid
    with rasterio.open(item.assets["B04"].href) as ref:
        ref_crs = ref.crs
        # window covering bbox in ref CRS
        west, south, east, north = transform_bounds("EPSG:4326", ref_crs, *BBOX, densify_pts=21)
        # convert geographic bounds to pixel window
        row_start, col_start = ref.index(west, north)
        row_stop, col_stop = ref.index(east, south)
        row_start, row_stop = sorted([int(row_start), int(row_stop)])
        col_start, col_stop = sorted([int(col_start), int(col_stop)])
        # center a PATCH x PATCH window inside available data
        height = max(row_stop - row_start, PATCH)
        width = max(col_stop - col_start, PATCH)
        r0 = max(0, row_start + (height - PATCH) // 2)
        c0 = max(0, col_start + (width - PATCH) // 2)
        if r0 + PATCH > ref.height:
            r0 = max(0, ref.height - PATCH)
        if c0 + PATCH > ref.width:
            c0 = max(0, ref.width - PATCH)
        window = Window(c0, r0, PATCH, PATCH)
        transform = ref.window_transform(window)
        crs = ref.crs

        stack = np.zeros((14, PATCH, PATCH), dtype=np.float32)
        band_meta = []
        for i, key in enumerate(band_keys):
            arr = np.zeros((PATCH, PATCH), dtype=np.float32)
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
                # Scale reflectance-like values to ~0-1 if uint16
                if arr.max() > 1.5:
                    arr = arr / 10000.0
                fill_note = None
            else:
                fill_note = "zeros_fill_missing_L2A_B10"
            stack[i] = arr
            band_meta.append(
                {
                    "band": key,
                    "index": i + 1,
                    "max": float(arr.max()),
                    "min": float(arr.min()),
                    "fill": fill_note,
                }
            )

    # DEM + slope from Copernicus GLO-30
    dem_search = catalog.search(collections=["cop-dem-glo-30"], bbox=BBOX, max_items=3)
    dem_items = list(dem_search.items())
    if not dem_items:
        return {"ok": False, "blocker": "no_dem_items", "s2_item": item.id}

    dem = np.zeros((PATCH, PATCH), dtype=np.float32)
    dem_item = dem_items[0]
    dem_asset = dem_item.assets.get("data") or next(iter(dem_item.assets.values()))
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

    # Slope in degrees from DEM gradients at 10 m
    gy, gx = np.gradient(dem, 10.0, 10.0)
    slope = np.degrees(np.arctan(np.hypot(gx, gy))).astype(np.float32)
    stack[12] = slope
    stack[13] = dem
    stack = np.nan_to_num(stack, nan=1e-6)

    meta = {
        "ok": True,
        "s2_item": item.id,
        "dem_item": dem_item.id,
        "crs": str(crs),
        "transform": list(transform)[:6],
        "bbox_wgs84": BBOX,
        "shape": list(stack.shape),
        "bands": band_meta
        + [
            {"band": "slope_deg", "index": 13, "min": float(slope.min()), "max": float(slope.max())},
            {"band": "dem_m", "index": 14, "min": float(dem.min()), "max": float(dem.max())},
        ],
        "b10_zeros_fill": b10_filled,
        "domain_warning": (
            "Values are native STAC physical units (S2 reflectance-ish, DEM meters, slope degrees). "
            "L4S/DeepSlide training used competition HDF5 tensors with different scaling. "
            "Predictions are therefore domain-shifted and not scientifically comparable to L4S metrics."
            + (" B10 filled with zeros (absent from L2A)." if b10_filled else "")
        ),
    }
    np.save(OUT / "input_stack_14chw.npy", stack)
    # write input geotiff
    profile = {
        "driver": "GTiff",
        "height": PATCH,
        "width": PATCH,
        "count": 14,
        "dtype": "float32",
        "crs": crs,
        "transform": transform,
        "compress": "lzw",
    }
    with rasterio.open(OUT / "input_14band.tif", "w", **profile) as dst:
        dst.write(stack)
        dst.update_tags(NOTE="STAC-built 14-band stack for DeepSlide domain-shift test")

    meta["input_tif"] = str(OUT / "input_14band.tif")
    meta["stack_npy"] = str(OUT / "input_stack_14chw.npy")
    meta["_stack"] = stack
    meta["_transform"] = transform
    meta["_crs"] = crs
    return meta


def run_inference(stack_meta: dict) -> dict:
    import rasterio

    stack = stack_meta["_stack"]
    transform = stack_meta["_transform"]
    crs = stack_meta["_crs"]
    device = torch.device("cpu")
    t0 = time.perf_counter()
    model = build_model()
    load_weights(model, WEIGHTS)
    model.eval().to(device)
    load_s = time.perf_counter() - t0
    t1 = time.perf_counter()
    prob = predict_prob(model, stack, device)
    infer_s = time.perf_counter() - t1
    pred = (prob > 0.5).astype(np.uint8)

    # QA
    qa = {
        "empty_prediction": int(pred.sum()) == 0,
        "all_positive": int(pred.sum()) == pred.size,
        "prob_min": float(prob.min()),
        "prob_max": float(prob.max()),
        "prob_mean": float(prob.mean()),
        "pred_pos": int(pred.sum()),
        "has_nan_prob": bool(np.isnan(prob).any()),
        "has_inf_prob": bool(np.isinf(prob).any()),
    }

    out_tif = OUT / "prediction_georef.tif"
    profile = {
        "driver": "GTiff",
        "height": pred.shape[0],
        "width": pred.shape[1],
        "count": 2,
        "dtype": "float32",
        "crs": crs,
        "transform": transform,
        "compress": "lzw",
        "nodata": None,
    }
    with rasterio.open(out_tif, "w", **profile) as dst:
        dst.write(pred.astype(np.float32), 1)
        dst.write(prob.astype(np.float32), 2)
        dst.update_tags(
            BAND1="binary_mask_threshold_0_5",
            BAND2="uncalibrated_sigmoid_score",
            WARNING="NOT_CALIBRATED_RISK; DOMAIN_SHIFTED_VS_L4S_TRAINING",
            CRS=str(crs),
        )

    # Verify CRS round-trip
    with rasterio.open(out_tif) as src:
        written_crs = src.crs
        written_transform = src.transform
        align_ok = (written_crs is not None) and (str(written_crs) == str(crs))

    # Preview
    rgb = np.stack([stack[3], stack[2], stack[1]], axis=-1)  # B4,B3,B2 approx RGB
    rgb = np.clip(rgb, 0, np.percentile(rgb, 98))
    rgb = rgb / (rgb.max() + 1e-8)
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    axes[0].imshow(rgb)
    axes[0].set_title("S2 RGB (B4/B3/B2)")
    im = axes[1].imshow(prob, cmap="magma", vmin=0, vmax=1)
    axes[1].set_title("Uncalibrated score")
    fig.colorbar(im, ax=axes[1], fraction=0.046)
    axes[2].imshow(rgb)
    axes[2].imshow(np.ma.masked_where(pred == 0, pred), cmap="autumn", alpha=0.5)
    axes[2].set_title("Overlay >0.5")
    for ax in axes:
        ax.axis("off")
    fig.suptitle(
        f"Georef DeepSlide test | CRS={crs} | DOMAIN-SHIFTED | NOT validated risk",
        fontsize=9,
    )
    fig.tight_layout()
    preview = OUT / "preview_georef.png"
    fig.savefig(preview, dpi=140, bbox_inches="tight")
    plt.close(fig)

    return {
        "ok": True,
        "model_load_s": round(load_s, 3),
        "infer_s": round(infer_s, 3),
        "prediction_tif": str(out_tif),
        "preview": str(preview),
        "crs": str(crs),
        "transform": [float(x) for x in written_transform][:6],
        "crs_aligned_with_input": align_ok,
        "georeferenced": True,
        "qa": qa,
        "label": "uncalibrated_segmentation_score_not_risk",
        "domain_matched_to_deepslide_training": False,
    }


def main() -> int:
    report: dict = {"phase": "2_and_4", "acceptance": {}}
    try:
        stack_meta = fetch_stack()
    except Exception as exc:  # noqa: BLE001
        report["stack"] = {"ok": False, "blocker": "exception", "error": str(exc), "traceback": traceback.format_exc()}
        (OUT / "georef_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2

    # strip non-serializable
    serial = {k: v for k, v in stack_meta.items() if not k.startswith("_")}
    report["stack"] = serial
    if not stack_meta.get("ok"):
        report["acceptance"]["phase2_georeferenced_input_ok"] = False
        report["acceptance"]["phase2_reason"] = stack_meta.get("blocker")
        report["verdict"] = "BLOCKED"
        (OUT / "georef_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2

    # Phase 2 strict: band order OK, CRS OK, but domain match required for "compatible"
    report["acceptance"]["bands_present_14"] = True
    report["acceptance"]["crs_present"] = True
    report["acceptance"]["domain_matched_to_training"] = False
    report["acceptance"]["phase2_georeferenced_input_ok"] = False
    report["acceptance"]["phase2_reason"] = (
        "STAC stack has real CRS and 14 bands, but value domain does not match "
        "Landslide4Sense competition tensors used to train DeepSlide; "
        "competition scaling is unpublished. Not a defensible model-compatible input."
    )

    try:
        inf = run_inference(stack_meta)
    except Exception as exc:  # noqa: BLE001
        report["inference"] = {"ok": False, "error": str(exc), "traceback": traceback.format_exc()}
        report["verdict"] = "BLOCKED"
        (OUT / "georef_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 3

    report["inference"] = inf
    # Phase 4: georeferenced file written with CRS — technical yes; scientifically compatible — no
    report["acceptance"]["phase4_geotiff_has_real_crs"] = bool(inf.get("georeferenced"))
    report["acceptance"]["phase4_aligned"] = bool(inf.get("crs_aligned_with_input"))
    report["acceptance"]["phase4_scientifically_valid_map"] = False
    report["acceptance"]["phase4_reason"] = (
        "GeoTIFF carries real CRS and matches input affine, but predictions are domain-shifted "
        "uncalibrated scores, not validated landslide risk."
    )
    report["verdict"] = "TECHNICAL_GEOREF_OK_DOMAIN_BLOCKED"
    (OUT / "georef_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
