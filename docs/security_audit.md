# SSRI Security Audit Checklist

Date of last local review: 2026-09-07 (software review; not a penetration test).

## Authentication / authorization

| Check | Status |
|-------|--------|
| Production cannot disable auth | Present (`SSRI_AUTH_REQUIRE_IN_PRODUCTION`) |
| Development principal only when auth disabled | Present (`development` key in Docker E2E) |
| Job ownership isolation | Covered by unit tests |
| Admin cancel authorization | Uses `Role.ADMIN` |
| Client cannot assert `SCIENTIFICALLY_VALIDATED` when untrusted | Present |

## Input / path safety

| Check | Status |
|-------|--------|
| Path traversal rejection on checkpoint/features | Present |
| Object storage key `..` rejection | Present + tested |
| Polygon AOI size / vertex / self-intersection limits | Present + tested |
| Rate limiting on sync inference/assess | Present (enabled in production defaults) |

## Secrets

| Check | Status |
|-------|--------|
| `.env` gitignored | Present |
| `credentials/` expected gitignored | Verify `.gitignore` |
| Compose mounts secrets via env_file, not COPY | Present |
| Dockerfile does not COPY `.env` / credentials | Present |

## CORS / debug

| Check | Status |
|-------|--------|
| No public debug shell endpoints observed in `ssri_model.api` | OK |
| Compose binds API to localhost-mapped ports | Operator-controlled |

## Remaining risks (honest)

* Async/inference checkpoint loading uses `torch.load` without `weights_only=True` (pickle risk if untrusted files are accepted). Treat checkpoint paths as trusted operator inputs.
* Live GEE/OpenTopo credentials, if mis-mounted world-readable, are a secret-leak risk — mount read-only and restrict file modes.
* Development defaults (`SSRI_AUTH_ENABLED=false`) must never ship to production unchanged.
* Signed local URLs are `file://` style references, not CDN auth — use S3/minio for real signed URLs.

## Verdict for this audit pass

Software controls are directionally sound for a research/ops screening API.
**Not a substitute for** external pen-test, secret scanning in CI history, or cloud IAM review.
