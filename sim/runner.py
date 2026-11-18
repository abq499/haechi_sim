# sim/runner.py
import random
import time
from dataclasses import replace

from . import metrics
from .model import Simulation


def run_one(cfg, seed, campaign=""):
    """Run one (config, seed) cell and return a flat CSV row."""
    random.seed(seed)
    t0 = time.perf_counter()
    sim = Simulation(cfg, seed).run()
    row = {"campaign": campaign, "seed": seed}
    row.update(cfg.as_row())
    row.update(metrics.compute(sim))
    if "skew" in cfg.attack and cfg.delta_max > 0 and cfg.adversaries:
        clean = Simulation(replace(cfg, delta_max=0.0), seed).run()
        row.update(metrics.attack_induced(sim, clean, sim.adv_set))
    row["wall_s"] = time.perf_counter() - t0
    return row
