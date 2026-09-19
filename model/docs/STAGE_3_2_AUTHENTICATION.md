# Stage 3.2 — API Authentication & Authorization

Stage 3.2 adds API-key authentication and role-based authorization to the FastAPI service.

**API keys authenticate clients. They do not establish geological truth and do not change scientific validation status.**

## Architecture

```
Client (Authorization: Bearer <API_KEY>)
  │
  ▼
FastAPI
  │
  ▼
Authentication / Authorization (Stage 3.2)
  │
  ▼
Stage 3.0 Service Contracts
  │
  ▼
Stage 2.7 / Stage 2.8
```

Authentication occurs before inference execution and never modifies scientific validation status.

## API Key Format

```
ssri_<key_id>_<secret>
```

- `key_id`: 16-character hex identifier (safe to reference in audit logs)
- `secret`: cryptographically random URL-safe string (≥32 characters)

Redacted logging example: `ssri_abcd1234abcd1234_********`

## Key Generation

```python
from ssri_model.auth import generate_api_key, Role

generated = generate_api_key(role=Role.OPERATOR)
# generated.plaintext_key — show once to operator
# generated.record — persist hash only
```

Plaintext keys are never persisted automatically.

## Key Hashing

API key secrets are stored using **PBKDF2-HMAC-SHA256** (600,000 iterations) via Python's standard library.

Stored format:

```
pbkdf2_sha256$<iterations>$<salt>$<derived>
```

## Key Store

Development file-backed store (no database):

```json
{
  "keys": [
    {
      "key_id": "abcd1234abcd1234",
      "key_hash": "pbkdf2_sha256$...",
      "role": "operator",
      "enabled": true,
      "created_at": "2026-01-01T00:00:00+00:00",
      "expires_at": null,
      "description": "operator key"
    }
  ]
}
```

Configure via `SSRI_AUTH_KEY_STORE` or `AuthConfig.key_store_path`.

## Roles

| Role | Permissions |
|------|-------------|
| `viewer` | `READ_STATUS`, `READ_METADATA` |
| `operator` | viewer + `RUN_INFERENCE`, `RUN_BATCH` |
| `admin` | operator + `MANAGE_AUTH` (future key management) |

## Endpoint Access Matrix

| Endpoint | Auth | Permission |
|----------|------|------------|
| `GET /health` | Public | — |
| `GET /api/v1/health` | Public | — |
| `GET /api/v1/ready` | Public | — |
| `POST /api/v1/inference` | Required | `RUN_INFERENCE` |
| `GET /api/v1/inference/{id}` | Required | `READ_METADATA` |
| `POST /api/v1/batch` | Required | `RUN_BATCH` |
| `GET /api/v1/batch/{id}/status` | Required | `READ_STATUS` |
| `GET /api/v1/batch/{id}/jobs/{job_id}` | Required | `READ_STATUS` |

## Development Configuration

```bash
SSRI_AUTH_ENABLED=false          # development only
SSRI_AUTH_KEY_STORE=auth/keys.json
SSRI_API_ENVIRONMENT=development
```

When auth is disabled in development, an explicit `development` operator principal is injected.

## Production Requirements

- `environment=production` requires `auth_enabled=true`
- Key store file must exist and contain hashed keys only
- Authentication cannot be silently disabled

## Authentication Errors

401 Unauthorized:

```json
{
  "error": {
    "code": "AUTHENTICATION_REQUIRED",
    "message": "Authentication is required.",
    "details": {}
  }
}
```

403 Forbidden (authorization):

```json
{
  "error": {
    "code": "INSUFFICIENT_PERMISSIONS",
    "message": "The authenticated principal does not have permission to perform this operation.",
    "details": {}
  }
}
```

Generic failure messages — no key existence/expiry hints for invalid credentials.

## Example Request

```bash
curl \
  -H "Authorization: Bearer <API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"request_id":"req-1", ...}' \
  http://localhost:8000/api/v1/inference
```

Never pass API keys in query parameters or URL paths.

## Audit Metadata

Structured logs (no secrets):

```json
{
  "event": "authentication",
  "request_id": "...",
  "key_id": "abcd1234abcd1234",
  "role": "operator",
  "endpoint": "/api/v1/inference",
  "method": "POST",
  "outcome": "success"
}
```

## Provenance Extension

Authenticated inference records optional provenance fields:

- `auth_key_id`
- `auth_role`
- `auth_method`

Reproducibility fingerprints are unchanged.

## Testing

```bash
poetry run pytest tests/test_auth_*.py tests/test_api_auth*.py tests/test_api_authentication.py tests/test_api_authorization.py -q
```

## Security Limitations

- File-backed key store (not HA/production IAM)
- No key management HTTP endpoints yet
- No rate limiting or OAuth/JWT
- Synchronous execution unchanged from Stage 3.1

## Future Stage

Stage 3.3+ may add key management endpoints, rate limiting, and deployment hardening.

## Package Location

`model/src/ssri_model/auth/`
