#!/usr/bin/env python3
"""Measure basic API latency percentiles (p50/p95/p99).

Usage (stack must be running):

  poetry run python scripts/measure_performance.py --base-url http://127.0.0.1:8000

Does not invent numbers — prints only measured samples.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.error
import urllib.request
from typing import Any


def _percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return float("nan")
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def timed_get(url: str, timeout: float = 10.0) -> tuple[float, int]:
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            _ = response.read()
            status = int(response.status)
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
    except Exception:
        status = 0
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return elapsed_ms, status


def summarize(name: str, samples_ms: list[float], ok_count: int) -> dict[str, Any]:
    ordered = sorted(samples_ms)
    return {
        "endpoint": name,
        "n": len(samples_ms),
        "ok": ok_count,
        "p50_ms": round(_percentile(ordered, 50), 3),
        "p95_ms": round(_percentile(ordered, 95), 3),
        "p99_ms": round(_percentile(ordered, 99), 3),
        "mean_ms": round(statistics.fmean(samples_ms), 3) if samples_ms else None,
        "max_ms": round(max(samples_ms), 3) if samples_ms else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--samples", type=int, default=30)
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    results: list[dict[str, Any]] = []
    for path in ("/health", "/api/v1/health", "/api/v1/ready"):
        samples: list[float] = []
        ok = 0
        for _ in range(args.samples):
            ms, status = timed_get(f"{base}{path}")
            samples.append(ms)
            if 200 <= status < 300:
                ok += 1
        results.append(summarize(path, samples, ok))

    print(json.dumps({"base_url": base, "results": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
