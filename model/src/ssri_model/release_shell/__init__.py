"""Upload-and-train release shell (gated by SSRI_RELEASE_SHELL).

Default production behaviour is unchanged when the flag is off.
"""

from __future__ import annotations

from ssri_model.release_shell.flags import (
    release_shell_enabled,
    release_shell_min_blocks,
    release_shell_min_held_out_blocks,
    release_shell_min_tiles,
    use_assess_softmax,
)

__all__ = [
    "release_shell_enabled",
    "use_assess_softmax",
    "release_shell_min_tiles",
    "release_shell_min_blocks",
    "release_shell_min_held_out_blocks",
]
