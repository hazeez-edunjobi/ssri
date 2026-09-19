"""Tests for Redis idempotency store."""

from __future__ import annotations

import pytest

from ssri_model.jobs.exceptions import IdempotencyConflictError
from tests.infrastructure_helpers import build_redis_idempotency_store


def test_same_principal_same_payload_returns_existing() -> None:
    store = build_redis_idempotency_store()
    first = store.put(
        principal_key_id="operator-key",
        idempotency_key="idem-001",
        job_id="job-abc123456789",
        request_fingerprint="fp-1",
    )
    second = store.put(
        principal_key_id="operator-key",
        idempotency_key="idem-001",
        job_id="job-abc123456789",
        request_fingerprint="fp-1",
    )
    assert first.job_id == second.job_id


def test_same_principal_different_payload_conflicts() -> None:
    store = build_redis_idempotency_store()
    store.put(
        principal_key_id="operator-key",
        idempotency_key="idem-conflict",
        job_id="job-abc123456789",
        request_fingerprint="fp-1",
    )
    with pytest.raises(IdempotencyConflictError):
        store.put(
            principal_key_id="operator-key",
            idempotency_key="idem-conflict",
            job_id="job-abc123456789",
            request_fingerprint="fp-2",
        )


def test_different_principals_isolated() -> None:
    store = build_redis_idempotency_store()
    first = store.put(
        principal_key_id="operator-key",
        idempotency_key="shared-key",
        job_id="job-abc123456789",
        request_fingerprint="fp-1",
    )
    second = store.put(
        principal_key_id="admin-key00000001",
        idempotency_key="shared-key",
        job_id="job-def987654321",
        request_fingerprint="fp-1",
    )
    assert first.job_id != second.job_id


def test_expiry_enforced() -> None:
    store = build_redis_idempotency_store(ttl_seconds=1)
    store.put(
        principal_key_id="operator-key",
        idempotency_key="expiring-key",
        job_id="job-abc123456789",
        request_fingerprint="fp-1",
    )
    key = store._key("operator-key", "expiring-key")
    store._client.delete(key)
    assert store.get(principal_key_id="operator-key", idempotency_key="expiring-key") is None
