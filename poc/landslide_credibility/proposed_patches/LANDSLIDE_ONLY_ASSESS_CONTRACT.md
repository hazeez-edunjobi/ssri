# Landslide-only assess contract (PROPOSED, not applied)

## Behaviour
- Landslide: optional susceptibility index path (future) — not wired in this task.
- Subsidence: return `availability: not_available` (no score).
- Sinkhole: return `availability: not_available` (no score).

## Framing (required)
\"relative landslide susceptibility index, derived from terrain/environment, validated only on CONUS held-out blocks (if Tier A or B), not a probability and not a risk estimate\"

## Softmax
Build on SOFTMAX_CONTRACT_PATCH.md — Stage 2.5 CE classes use softmax, not sigmoid.
