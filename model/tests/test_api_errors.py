"""Tests for SSRI API error handling."""

from __future__ import annotations


from ssri_model.api.errors import sanitize_error_message
from tests.api_helpers import create_test_client


def test_error_schema_for_validation_error(tmp_path) -> None:
    client = create_test_client(tmp_path)
    response = client.post("/api/v1/inference", json={})
    assert response.status_code == 422
    payload = response.json()
    assert "error" in payload
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert "message" in payload["error"]


def test_sanitize_error_message_strips_paths() -> None:
    message = sanitize_error_message("Failed at C:\\Users\\secret\\checkpoint.pt")
    assert "C:\\Users" not in message
    assert "<path>" in message


def test_no_stack_trace_in_error_response(tmp_path) -> None:
    client = create_test_client(tmp_path)
    response = client.post("/api/v1/inference", json={"request_id": "x"})
    body = response.text
    assert "Traceback" not in body
    assert "File \"" not in body
