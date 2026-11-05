# CI note — DeepSlide optional dependencies

**Choice:** optional Poetry group `deepslide` (not production deps).

```bash
poetry -C model install --with deepslide
```

Packages: `segmentation-models-pytorch`, `h5py`.

`poc/release_shell/scripts/verify.py` probes these imports. If missing, it records  
`DeepSlide skipped: optional deps` with **returncode 0** and does **not** fail the verify gate.  
When deps are present, the 9 DeepSlide engine tests must pass.

Release-shell / assess / Stage 2.5 paths do not import DeepSlide.
