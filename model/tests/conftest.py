"""Shared pytest fixtures for SSRI model tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_release_shell_env(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    """Keep legacy assess behaviour stable unless the test is release-shell-aware.

    Release-shell tests set ``SSRI_RELEASE_SHELL`` themselves after this fixture runs.
    Ambient process env (e.g. a flag-ON CI matrix) must not change the default-off suite.
    """
    nodeid = request.node.nodeid.replace("\\", "/")
    if "test_release_shell" in nodeid or "/release_shell/" in nodeid:
        return
    monkeypatch.delenv("SSRI_RELEASE_SHELL", raising=False)
    monkeypatch.delenv("SSRI_ASSESS_SOFTMAX", raising=False)
