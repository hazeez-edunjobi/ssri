from __future__ import annotations

from pathlib import Path

p = Path(r"C:/Users/LENOVO/Documents/MrBusoye/ssri/data/geophysics/raw/WGM2012_Bouguer_ponc_2min.grd")
print("size", p.stat().st_size)
try:
    import netCDF4 as nc

    ds = nc.Dataset(str(p))
    print("vars", list(ds.variables.keys()))
    for k, v in ds.variables.items():
        print(k, v.dimensions, v.shape)
except Exception as exc:
    print("netcdf_err", type(exc).__name__, exc)

try:
    import xarray as xr

    dsx = xr.open_dataset(p)
    print("xarray", dsx)
except Exception as exc:
    print("xarray_err", type(exc).__name__, exc)
