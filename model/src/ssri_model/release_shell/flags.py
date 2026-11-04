"""Feature flags for the release shell (default OFF)."""

from __future__ import annotations

import os


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def release_shell_enabled() -> bool:
    """Master switch for upload-and-train shell behaviour."""
    return _env_flag("SSRI_RELEASE_SHELL", default=False)


def use_assess_softmax() -> bool:
    """Use softmax (eval contract) in assess/MC paths.

    Enabled when ``SSRI_RELEASE_SHELL`` or ``SSRI_ASSESS_SOFTMAX`` is true.
    Default false preserves legacy sigmoid behaviour.
    """
    return release_shell_enabled() or _env_flag("SSRI_ASSESS_SOFTMAX", default=False)


def release_shell_min_tiles() -> int:
    """Minimum labelled tiles per hazard (default 300)."""
    return int(os.getenv("SSRI_RELEASE_SHELL_MIN_TILES", "300"))


def release_shell_min_blocks() -> int:
    """Minimum distinct 5° blocks (default 8)."""
    return int(os.getenv("SSRI_RELEASE_SHELL_MIN_BLOCKS", "8"))


def release_shell_min_held_out_blocks() -> int:
    """Minimum held-out blocks for eval (default 3)."""
    return int(os.getenv("SSRI_RELEASE_SHELL_MIN_HELD_OUT", "3"))


def release_shell_buffer_km() -> float:
    return float(os.getenv("SSRI_RELEASE_SHELL_BUFFER_KM", "50"))


def default_limitations() -> list[str]:
    return [
        "trained only on the uploaded data's geography; not validated elsewhere",
        "slope alone often matches or beats trained models",
        "scores are relative susceptibility rankings, not probabilities or risk estimates",
        "scientific status remains NOT_VALIDATED; not independently reviewed",
        "must never be used for insurance, engineering, safety, or emergency decisions",
    ]
