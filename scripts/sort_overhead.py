# scripts/sort_overhead.py — todo B9 (E8): wall-clock cost of sorting one round by the DLO key.
import csv
import os
import platform
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPS = 100


def round_keys(N, n_shards, rng):
    """N transactions of one round: (R, B, pi(S), T) with R fixed and B in {r-1, r}."""
    s = rng.integers(0, n_shards, N)
    b = 100 - (rng.random(N) < 0.05)
    t = rng.integers(0, max(1, N // n_shards), N)
    return [(100, int(bi), int(si), int(ti)) for bi, si, ti in zip(b, s, t)]


def main():
    rng = np.random.default_rng(0)
    rows = []
    for N in [10**2, 10**3, 10**4, 10**5]:
        keys = round_keys(N, 30, rng)
        times = []
        for _ in range(REPS):
            data = list(keys)
            rng.shuffle(data)
            t0 = time.perf_counter()
            data.sort()
            times.append((time.perf_counter() - t0) * 1e3)
        rows.append({"N": N, "reps": REPS, "sort_ms_median": float(np.median(times)),
                     "sort_ms_p99": float(np.percentile(times, 99)),
                     "python": sys.version.split()[0], "processor": platform.processor()})
        print(rows[-1])
    out = os.path.join(ROOT, "results", "raw", "E8_sort_overhead.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
