"""Feature attribution: SHAP when available, else input gradients.

PRD prefers SHAP. Runtime must not invent attribution values. If ``shap`` is
not installed, callers should use :func:`gradient_feature_attribution` from
``ssri_model.uncertainty`` and record the method in metadata.
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import torch
from torch import nn

from ssri_model.ml.constants import CHANNEL_NAMES
from ssri_model.uncertainty import gradient_feature_attribution


def attribution_backend_available() -> dict[str, bool]:
    try:
        import shap  # noqa: F401
    except ImportError:
        return {"shap": False, "gradient": True}
    return {"shap": True, "gradient": True}


def attribute_top_channels(
    model: nn.Module,
    features: torch.Tensor,
    *,
    class_index: int,
    top_k: int = 3,
) -> tuple[list[str], str]:
    """Return ``(top channel names, method_id)``.

    Attempts SHAP DeepExplainer when the ``shap`` package is importable and the
    model is compatible; otherwise uses input-gradient magnitudes.
    """
    backends = attribution_backend_available()
    if backends["shap"]:
        try:
            names = _shap_top_channels(
                model, features, class_index=class_index, top_k=top_k
            )
            return names, "shap_deep_explainer"
        except Exception:
            # Fall through to gradients — do not fabricate SHAP numbers.
            pass
    ranked = gradient_feature_attribution(model, features, class_index=class_index)
    return list(ranked[:top_k]), "input_gradient"


def _shap_top_channels(
    model: nn.Module,
    features: torch.Tensor,
    *,
    class_index: int,
    top_k: int,
) -> list[str]:
    import shap

    model.eval()
    background = features[: min(8, features.shape[0])].detach()

    def predict(x: np.ndarray) -> np.ndarray:
        tensor = torch.from_numpy(x).to(dtype=features.dtype, device=features.device)
        with torch.no_grad():
            logits = model(tensor)
            if logits.ndim == 4:
                probs = torch.sigmoid(logits[:, class_index].mean(dim=(1, 2)))
            else:
                probs = torch.sigmoid(logits[:, class_index])
        return probs.detach().cpu().numpy()

    explainer = shap.DeepExplainer(model, background)
    # DeepExplainer expects tensors for some models; keep numpy path via GradientExplainer fallback
    try:
        shap_values = explainer.shap_values(features[:1])
    except Exception:
        explainer = shap.GradientExplainer(model, background)
        shap_values = explainer.shap_values(features[:1])

    values = shap_values
    if isinstance(values, list):
        values = values[min(class_index, len(values) - 1)]
    arr = np.asarray(values)
    if arr.ndim >= 4:
        channel_scores = np.abs(arr).mean(axis=(0, 2, 3))
    else:
        channel_scores = np.abs(arr).reshape(arr.shape[0], -1).mean(axis=0)
    order = np.argsort(-channel_scores)
    names: list[str] = []
    for idx in order:
        if idx < len(CHANNEL_NAMES):
            names.append(CHANNEL_NAMES[int(idx)])
        if len(names) >= top_k:
            break
    return names
