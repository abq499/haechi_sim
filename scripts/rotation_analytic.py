# scripts/rotation_analytic.py — todo B7 (E6) for long horizons.
"""In a homogeneous run every round contains all n shards, so the round winner is the shard
with the smallest pi_e(S); it is fixed for the epoch. Win rates therefore follow directly from
sim.model.rotated_permutation (the generator the Beacon uses), without simulating rounds.
E6_rotation cross-checks this against full simulations on short horizons."""
import csv
import os
import sys

import numpy as np
from scipy import stats

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sim.model import rotated_permutation  # noqa: E402


def winners(policy, n, epochs, seed):
    if policy == "static":
        return np.zeros(epochs, dtype=int)
    if policy == "cyclic":  # (S + e) % n is smallest for S = -e mod n
        return (-np.arange(epochs)) % n
    return np.array([int(np.argmin(rotated_permutation(seed, e, n))) for e in range(epochs)])


def main():
    rows = []
    for n in [10, 20, 30]:
        for epochs in [10, 100, 1000]:
            for policy in ["static", "cyclic", "rotated"]:
                for seed in range(30):
                    counts = np.bincount(winners(policy, n, epochs, seed), minlength=n)
                    rates = counts / epochs
                    p = stats.chisquare(counts).pvalue if counts.sum() else float("nan")
                    rows.append({"n": n, "epochs": epochs, "policy": policy, "seed": seed,
                                 "win_rate_s0": rates[0], "win_rate_max": rates.max(),
                                 "win_rate_min": rates.min(), "chi2_p": p})
    out = os.path.join(ROOT, "results", "raw", "E6_rotation_analytic.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
