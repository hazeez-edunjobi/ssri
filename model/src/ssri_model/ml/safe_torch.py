"""Safe torch checkpoint loading with explicit trust boundary.

SSRI checkpoints are operator-supplied trusted artifacts. Prefer
``weights_only=True`` when the torch version supports it; fall back to the
legacy loader only for older checkpoints that still require full unpickling.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import torch


def load_torch_checkpoint(
    path: Path | str,
    *,
    map_location: str | torch.device = "cpu",
) -> dict[str, Any]:
    """Load a checkpoint dict from disk.

    Trust boundary: callers must ensure ``path`` is an operator-controlled
    artifact. Do not pass untrusted user uploads here.
    """
    destination = Path(path)
    try:
        payload = torch.load(destination, map_location=map_location, weights_only=True)
    except TypeError:
        # Older torch without weights_only=
        payload = torch.load(destination, map_location=map_location)
    except Exception:
        # Legacy SSRI checkpoints may contain non-tensor metadata requiring full load.
        payload = torch.load(destination, map_location=map_location, weights_only=False)
    if not isinstance(payload, dict):
        raise TypeError(f"Checkpoint payload must be a dict, got {type(payload).__name__}")
    return cast(dict[str, Any], payload)
