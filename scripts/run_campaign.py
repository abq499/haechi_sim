# scripts/run_campaign.py
"""Run campaigns in parallel and write one CSV row per (cell, seed) to results/raw/<name>.csv.

    python scripts/run_campaign.py                 # all campaigns
    python scripts/run_campaign.py A_skew E1_rofvr --seeds 30 --workers 10
"""
import argparse
import csv
import json
import os
import platform
import sys
import time
from multiprocessing import Pool

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from configs.campaigns import CAMPAIGNS  # noqa: E402
from sim import run_one  # noqa: E402


def _job(args):
    name, cfg, seed = args
    return run_one(cfg, seed, campaign=name)


def write_csv(path, rows):
    keys = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def write_env(out_dir, seeds):
    import numpy, scipy, simpy
    env = {
        "python": sys.version.split()[0], "simpy": simpy.__version__, "numpy": numpy.__version__,
        "scipy": scipy.__version__, "platform": platform.platform(),
        "processor": platform.processor(), "cpu_count": os.cpu_count(), "seeds": seeds,
    }
    with open(os.path.join(out_dir, "env.json"), "w", encoding="utf-8") as f:
        json.dump(env, f, indent=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*", default=list(CAMPAIGNS))
    ap.add_argument("--seeds", type=int, default=30)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--out", default=os.path.join(ROOT, "results", "raw"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    seeds = list(range(a.seeds))
    write_env(os.path.dirname(a.out), seeds)
    with Pool(a.workers) as pool:
        for name in a.names:
            jobs = [(name, cfg, s) for cfg in CAMPAIGNS[name]() for s in seeds]
            t0 = time.perf_counter()
            rows = pool.map(_job, jobs, chunksize=4)
            write_csv(os.path.join(a.out, f"{name}.csv"), rows)
            print(f"{name}: {len(rows)} runs in {time.perf_counter() - t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
