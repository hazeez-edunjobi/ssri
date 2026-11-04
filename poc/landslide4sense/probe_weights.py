import segmentation_models_pytorch as smp
import torch
from pathlib import Path

out = Path(__file__).resolve().parent / "outputs"
out.mkdir(parents=True, exist_ok=True)
log = out / "load_probe.txt"

s = torch.load(
    Path(__file__).resolve().parent / "weights" / "mobilenetv2.pth",
    map_location="cpu",
    weights_only=False,
)
odd = [k for k in s if not k.startswith("model.model.")]
lines = [
    f"total_keys={len(s)}",
    f"odd n={len(odd)} sample={odd[:30]}",
    f"n model.model={sum(1 for k in s if k.startswith('model.model.'))}",
]

m = smp.Unet(
    encoder_name="mobilenet_v2",
    encoder_weights=None,
    in_channels=14,
    classes=1,
)
cand = {k[len("model.model.") :]: v for k, v in s.items() if k.startswith("model.model.")}
miss, unexp = m.load_state_dict(cand, strict=False)
lines.append(f"missing={len(miss)} unexpected={len(unexp)}")
lines.append("miss " + str(miss[:20]))
lines.append("unexp " + str(unexp[:20]))
# param count match
loaded = sum(p.numel() for p in m.parameters())
lines.append(f"model_params={loaded}")
log.write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
