# tests/test_sim.py — run with: python -m unittest discover -s tests -v
import itertools
import os
import sys
import unittest
from dataclasses import replace

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.append(os.path.join(ROOT, "legacy"))  # old evaluation.py / models.py, used as a cross-check

from sim import SimConfig  # noqa: E402
from sim.metrics import count_pairs_gt, fvr_same_height  # noqa: E402
from sim.model import Simulation  # noqa: E402

BASE = SimConfig(n=6, engine="dlo", workload="poisson", rate=2.0, offset_mode="random",
                 eps=0.05, adversaries=(5,), delta_max=1.0, sim_time=120)


def order(cfg, seed):
    return [x.tid for x in Simulation(cfg, seed).run().beacon.out]


class TestMetrics(unittest.TestCase):
    def test_count_pairs_matches_brute_force(self):
        rng = np.random.default_rng(0)
        for size, gap in itertools.product([0, 1, 7, 64, 65, 300], [0.0, 0.3, 2.0]):
            a = rng.uniform(0, 5, size).round(1)  # rounding creates ties
            w = rng.integers(0, 2, size)
            brute = sum(w[j] for i in range(size) for j in range(i + 1, size) if a[i] > a[j] + gap)
            self.assertEqual(count_pairs_gt(a, w, gap), brute)

    def test_same_height_fvr_matches_old_evaluation(self):
        from evaluation import calculate_fvr
        from models import Transaction
        cfg = replace(BASE, engine="haechi_round", workload="per_block", offset_mode="id",
                      sim_time=60)
        out = Simulation(cfg, 3).run().beacon.out
        old = [Transaction(f"S{x.shard}-{x.B}-{x.T}", x.cut) for x in out]
        p, v = fvr_same_height(out)
        self.assertAlmostEqual(100.0 * v / p, calculate_fvr(old))


class TestLemma1(unittest.TestCase):
    def check(self, cfg, seed):
        out = Simulation(cfg, seed).run().beacon.out
        self.assertTrue(out)
        for x in out:
            self.assertGreaterEqual(x.R, x.B)
        rs = [x.R for x in out]
        self.assertEqual(rs, sorted(rs))  # smaller R always precedes
        return out

    def test_round_monotonicity_with_timeouts(self):
        for seed in range(5):
            cfg = replace(BASE, tau_max=0.3, delay_dist="pareto", slow_shards=(1,), slow_mult=2.0)
            out = self.check(cfg, seed)
            self.assertTrue(any(x.R > x.B for x in out), "expected late admissions")

    def test_no_timeout_gives_R_equal_B(self):
        for seed in range(5):
            out = self.check(replace(BASE, tau_max=None, delay_dist="pareto"), seed)
            self.assertTrue(all(x.R == x.B for x in out))

    def test_no_timeout_static_reduces_to_BST(self):
        for seed in range(5):
            out = Simulation(replace(BASE, tau_max=None), seed).run().beacon.out
            keys = [(x.B, x.shard, x.T) for x in out]
            self.assertEqual(keys, sorted(keys))


class TestTheorem1(unittest.TestCase):
    def test_skew_independence(self):
        """Executions differing only in blockTS produce the same DLO output."""
        for seed, prio, tau in itertools.product(range(4), ["static", "rotated"], [None, 0.5]):
            cfg = replace(BASE, priority=prio, tau_max=tau, delay_dist="lognormal")
            ref = order(replace(cfg, delta_max=0.0), seed)
            for dm in (0.1, 1.0, 3.0):
                self.assertEqual(order(replace(cfg, delta_max=dm), seed), ref)

    def test_skew_changes_timestamp_order(self):
        """Sanity check: the same perturbation does change timestamp ordering."""
        cfg = replace(BASE, engine="haechi_round")
        self.assertNotEqual(order(replace(cfg, delta_max=0.0), 1),
                            order(replace(cfg, delta_max=1.0), 1))

    def test_agreement_deterministic(self):
        cfg = replace(BASE, priority="rotated", tau_max=0.5)
        self.assertEqual(order(cfg, 9), order(cfg, 9))


class TestTheorem2(unittest.TestCase):
    def test_no_violation_outside_window(self):
        """Uniform delay (tau = 0.05), lockstep eps, tau_max >= eps + tau + Delta."""
        from sim import run_one
        for seed, n, dm in itertools.product(range(3), [3, 10], [0.1, 1.0]):
            cfg = replace(BASE, n=n, adversaries=(n - 1,), delta_max=dm,
                          tau_max=0.05 + 0.05 + dm, priority="rotated")
            row = run_one(cfg, seed)
            self.assertEqual(row["viol_out_W"], 0)
            self.assertLessEqual(row["max_inv_gap"], row["W"])


class TestAttackInduced(unittest.TestCase):
    def test_counterfactual_runs_share_transactions(self):
        cfg = replace(BASE, engine="haechi_round", tau_max=1.1)
        att = Simulation(cfg, 2).run()
        clean = Simulation(replace(cfg, delta_max=0.0), 2).run()
        a = {x.tid: (x.shard, x.t, x.B, x.T) for x in att.all_tx}
        c = {x.tid: (x.shard, x.t, x.B, x.T) for x in clean.all_tx}
        self.assertEqual(a, c)

    def test_dlo_zero_timestamp_engines_positive(self):
        from sim import run_one
        for seed, prio in itertools.product(range(3), ["static", "rotated"]):
            row = run_one(replace(BASE, priority=prio, tau_max=1.1), seed)
            self.assertEqual(row["a_flips"], 0)
            self.assertEqual(row["a_fvr"], 0.0)
        for eng in ["haechi_round", "haechi"]:
            row = run_one(replace(BASE, engine=eng, tau_max=1.1), 0)
            self.assertGreater(row["a_fvr"], 0.0)

    def test_gap_histogram_is_cumulative(self):
        from sim import run_one
        row = run_one(replace(BASE, n=10, adversaries=(9,), tau_max=1.1), 1)
        counts = [row["n_viol_ro"]] + [row[f"inv_gap_gt_{g}"] for g in (0.5, 1.0, 2.0, 3.0, 4.0)]
        self.assertEqual(counts, sorted(counts, reverse=True))


class TestRotation(unittest.TestCase):
    def test_cyclic_reproduces_old_simulator(self):
        """Old rule (S + h // 100) % n over ~499 heights gives shard 0 first in 99 of them."""
        from sim import run_one
        cfg = SimConfig(n=10, engine="dlo", priority="cyclic", epoch_len=100, sim_time=1000)
        row = run_one(cfg, 0)
        self.assertAlmostEqual(row["win_rate_s0"], 99 / 499, places=3)


if __name__ == "__main__":
    unittest.main()
