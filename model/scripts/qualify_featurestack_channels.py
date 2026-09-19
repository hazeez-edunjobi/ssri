"""FeatureStack channel source audit (no fabricated data)."""

from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv() -> None:
    root = Path(__file__).resolve().parents[2]
    env_path = root / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


CHANNELS = [
    ("elevation", "OpenTopography DEM", "external", "OPENTOPOGRAPHY_API_KEY"),
    ("slope", "derived from DEM", "derived", "OPENTOPOGRAPHY_API_KEY"),
    ("plan_curvature", "derived from DEM", "derived", "OPENTOPOGRAPHY_API_KEY"),
    ("profile_curvature", "derived from DEM", "derived", "OPENTOPOGRAPHY_API_KEY"),
    ("twi", "derived from DEM", "derived", "OPENTOPOGRAPHY_API_KEY"),
    ("relative_relief", "derived from DEM", "derived", "OPENTOPOGRAPHY_API_KEY"),
    ("valley_depth", "derived from DEM", "derived", "OPENTOPOGRAPHY_API_KEY"),
    ("ndvi", "GEE Sentinel-2", "external", "GEE credentials"),
    ("ndwi", "GEE Sentinel-2", "external", "GEE credentials"),
    ("clay_mineral_ratio", "GEE Sentinel-2", "external", "GEE credentials"),
    ("iron_oxide_index", "GEE Sentinel-2", "external", "GEE credentials"),
    (
        "gravity",
        "WGM2012 Complete Spherical Bouguer via GRAVITY_DATA_PATH",
        "local_raster",
        "GRAVITY_DATA_PATH",
    ),
    (
        "magnetics",
        "EMAG2v3 UC 4km via MAGNETIC_DATA_PATH",
        "local_raster",
        "MAGNETIC_DATA_PATH",
    ),
]


def _present(name: str) -> bool:
    root = Path(__file__).resolve().parents[2]
    if name == "GEE credentials":
        path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or os.getenv("GEE_PRIVATE_KEY_PATH")
        sa = os.getenv("GEE_SERVICE_ACCOUNT")
        project = os.getenv("GCP_PROJECT_ID") or os.getenv("GEE_PROJECT")
        candidates = [root / "credentials" / "earth-engine.json"]
        if path:
            p = Path(path)
            candidates.append(p if p.is_absolute() else root / p)
            candidates.append(p)
        file_ok = any(c.is_file() for c in candidates)
        return file_ok and bool(sa) and bool(project)
    if name == "OPENTOPOGRAPHY_API_KEY":
        return bool(os.getenv("OPENTOPOGRAPHY_API_KEY"))
    value = os.getenv(name)
    defaults = {
        "GRAVITY_DATA_PATH": root
        / "data"
        / "geophysics"
        / "processed"
        / "lagos_gravity_wgm2012_bouguer.tif",
        "MAGNETIC_DATA_PATH": root
        / "data"
        / "geophysics"
        / "processed"
        / "lagos_magnetic_emag2v3_uc4km.tif",
    }
    candidates: list[Path] = []
    if value:
        path = Path(value)
        candidates.append(path if path.is_absolute() else root / path)
    if name in defaults:
        candidates.append(defaults[name])
    return any(c.is_file() for c in candidates)


def _gee_init_status() -> str:
    try:
        from ssri_model.data.gee_client import GEEInitializationError, initialize

        initialize()
        return "INIT_OK"
    except Exception as exc:  # noqa: BLE001 — audit script
        name = type(exc).__name__
        cause = str(exc)
        if name == "GEEInitializationError" or "Earth Engine" in cause:
            if "serviceUsageConsumer" in cause or "permission" in cause.lower():
                return "INIT_BLOCKED_IAM"
            return "INIT_FAIL"
        return f"INIT_FAIL:{name}"


def main() -> int:
    _load_dotenv()
    print("FEATURESTACK_CHANNEL_AUDIT")
    blocked = []
    gee_status = None
    for channel, source, kind, requirement in CHANNELS:
        ok = _present(requirement)
        if requirement == "GEE credentials" and ok:
            if gee_status is None:
                gee_status = _gee_init_status()
            status = "LIVE_READY" if gee_status == "INIT_OK" else gee_status
            if gee_status != "INIT_OK":
                blocked.append(channel)
        elif ok:
            status = "CONFIG_PRESENT"
        else:
            status = "MISSING_INPUT"
            blocked.append(channel)
        print(f"{channel}\tsource={source}\tkind={kind}\tstatus={status}")
    print(f"BLOCKED_CHANNELS={','.join(blocked) if blocked else 'none'}")
    print(
        "NOTE=zeros/nodata fill is not enabled for missing gravity/magnetics; "
        "pipeline raises GeophysicsConfigError instead."
    )
    if gee_status:
        print(f"GEE_RUNTIME={gee_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
