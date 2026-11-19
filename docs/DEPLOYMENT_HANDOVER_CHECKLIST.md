# Deployment & handover checklist

Do **not** treat this as hosted verification. Fill after tomorrow’s deployment against the live environment.

## Environment

- [ ] `SSRI_OUTPUT_ROOT` persistent volume
- [ ] Postgres + Redis for distributed jobs (`SSRI_INTEGRATION_TESTS` path)
- [ ] `SSRI_AUTH_ENABLED` / API keys as required
- [ ] Supabase URL + anon (browser) and service-role (server only)
- [ ] CORS origins for the frontend domain
- [ ] Optional: `SSRI_UPLOAD_MAX_BYTES`, `SSRI_UPLOAD_MAX_ROWS`
- [ ] Optional: `SSRI_RELEASE_SHELL`, `SSRI_LIVE_ACQUISITION_ENABLED`
- [ ] GEE / OpenTopography / geophysics paths if live AOI is enabled

## Secrets (do not paste into reports)

- [ ] Supabase service role
- [ ] API / operator keys
- [ ] Object-storage credentials if used
- [ ] GEE service account / OpenTopography key

## Hosted smoke plan (post-deploy)

1. Health / readiness
2. Sign-in
3. Map click → assess with `location_provenance` echo
4. Labelled CSV upload → validate → train → promote → assess
5. Feature-only CSV refused for supervised train
6. Job cancel / retry once

## Client onboarding

See `docs/CLIENT_HANDOVER_ACCEPTANCE.md` and `docs/MANUAL_TRAINING_CLIENT_BRIEFING.md`.

## Known limitations register

- Research-ready, scientifically unvalidated
- Abeokuta CRS/units unconfirmed
- Live AOI depends on external DEM/GEE/geophysics
- Demo mode is not geospatial truth
- Column-mapping UI still alias-based
