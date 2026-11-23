# SSRI Deployment Readiness Guide

**This document prepares hosting. Do not deploy from this task.**

## Components to host

1. **Frontend** — Next.js production build (`npm run build` / `npm start` or static export host as configured).
2. **FastAPI** — `uvicorn ssri_model.api.app:app` behind HTTPS reverse proxy.
3. **Celery worker** — same codebase, queue `ssri_jobs`, shared filesystem with API for outputs.
4. **PostgreSQL** — platform auth/product schema (Supabase or self-hosted).
5. **Redis** — Celery broker/result (managed Redis / Upstash-compatible).
6. **Persistent storage** — `SSRI_OUTPUT_ROOT` for geological originals, derived rasters, training artefacts.

## Checklist before go-live

- [ ] `SSRI_AUTH_ENABLED` (or platform auth) enforced in production.
- [ ] Service-role keys never exposed to the browser.
- [ ] CORS limited to the real frontend origin(s).
- [ ] HTTPS certificates and domain DNS.
- [ ] Database migrations applied (`supabase/migrations/…`).
- [ ] Health/ready probes wired to the orchestrator.
- [ ] Shared volume between API and worker for `{output_root}`.
- [ ] Backup schedule for DB + output root + checkpoints.
- [ ] Demo mode disabled in production builds.
- [ ] Rollback: previous container images + DB snapshot + output snapshot.

## Environment groups

| Group | Examples |
|---|---|
| Public frontend | `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` |
| API secrets | DB URL, service role, auth flags, output root |
| Worker | Same as API for broker + output root |

## Suggested host steps (existing stack)

1. Provision Postgres; apply `supabase/migrations/` (including platform v4).
2. Provision Redis; set Celery broker/result URLs on API and worker.
3. Mount persistent disk at `SSRI_OUTPUT_ROOT` shared by API + worker.
4. Configure production env: auth on, demo off, development mode off, CORS allowlist, no wildcard.
5. Build frontend (`npm ci && npm run build`) and serve behind HTTPS.
6. Start API (`uvicorn ssri_model.api.app:app`) and Celery worker (`-Q ssri_jobs`).
7. Confirm `GET /api/v1/health` and `GET /api/v1/ready`.
8. Smoke: login → upload geological CSV → validate → process → download; assess with promoted checkpoint.

Do not deploy from this repository task — use the operator’s hosting runbook.

## Rollback

1. Stop traffic to new revision.
2. Redeploy previous API/frontend/worker images.
3. Restore DB snapshot if schema changed.
4. Confirm `/api/v1/health` and a smoke assess / geological list.

## Out of scope for first host

- Retraining Stage 2.5 models.
- Claiming scientific validation of TMI products.
- Contacting the client from the deployment pipeline.
