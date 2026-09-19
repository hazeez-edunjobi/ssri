# SSRI Authentication (Stage 3.2)

API-key authentication and role-based authorization at the HTTP boundary.

## Responsibilities

- Bearer API-key authentication
- PBKDF2-HMAC-SHA256 key hashing
- File-backed key store (development)
- Role/permission enforcement via FastAPI dependencies
- Structured audit logging (no secrets)

## Security

- Plaintext keys are never persisted
- Authorization headers are never logged
- Authentication does not imply scientific validation

See `model/docs/STAGE_3_2_AUTHENTICATION.md`.
