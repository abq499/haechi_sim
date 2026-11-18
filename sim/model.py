# sim/model.py
"""Shards, network and Beacon Chain engines (SimPy discrete-event model).

Time origin t0 = 0. Height h is nominally cut at t_h = h * lambda; shard i cuts it at
t_h * slow_mult + offset. The Beacon round r targets height r and its timeout is anchored
at the nominal schedule t_r + tau_max (Algorithm 1), not at the first arrival.
"""
import math
from collections import defaultdict

import numpy as np
import simpy


class Tx:
    __slots__ = ("tid", "shard", "t", "B", "T", "cut", "ts", "R", "emit", "pos",
                 "adv_tx", "target", "withheld")

    def __init__(self, tid, shard, t, adv_tx=False, target=None):
        self.tid = tid
        self.shard = shard          # S(x)
        self.t = t                  # t(x): first time x exists at any node
        self.adv_tx = adv_tx        # created by the adversary
        self.target = target        # insert attack: the honest tx being front-run
        self.withheld = False
        self.B = self.T = self.cut = self.ts = self.R = self.emit = self.pos = None


class CrossLink:
    __slots__ = ("s", "h", "ts", "cut", "txs", "arrive", "R")

    def __init__(self, s, h, ts, cut, txs):
        self.s, self.h, self.ts, self.cut, self.txs = s, h, ts, cut, txs
        self.arrive = self.R = None


def sample_delay(rng, dist):
    if dist == "uniform":
        return rng.uniform(0.01, 0.05)
    if dist == "lognormal":
        return rng.lognormal(math.log(0.05), 0.6)
    if dist == "pareto":
        return (rng.pareto(1.5) + 1.0) * 0.02
    raise ValueError(dist)


class Simulation:
    def __init__(self, cfg, seed):
        self.cfg = cfg
        self.seed = seed
        # Independent streams so that changing one lever (e.g. skew) leaves the others intact.
        ss = np.random.SeedSequence(seed)
        (self.rng_work, self.rng_off, self.rng_delay,
         self.rng_skew, self.rng_adv) = [np.random.default_rng(s) for s in ss.spawn(5)]
        self.env = simpy.Environment()
        self.adv_set = frozenset(cfg.adversaries)
        self.slow_set = frozenset(cfg.slow_shards)
        self.all_tx = []
        self.cut_hist = defaultdict(list)
        self.queues = self._make_workload()
        if cfg.engine == "dlo" or cfg.engine == "haechi_round":
            self.beacon = RoundBeacon(self)
        elif cfg.engine == "haechi":
            self.beacon = WatermarkBeacon(self)
        else:
            raise ValueError(cfg.engine)
        for s in range(cfg.n):
            self.env.process(self.shard_proc(s))

    # ---------------------------------------------------------------- workload
    def new_tx(self, shard, t, adv_tx=False, target=None):
        x = Tx(len(self.all_tx), shard, t, adv_tx, target)
        self.all_tx.append(x)
        return x

    def _make_workload(self):
        cfg = self.cfg
        queues = {s: [] for s in range(cfg.n)}
        if cfg.workload != "poisson":
            return queues
        for s in range(cfg.n):
            t = 0.0
            while True:
                t += self.rng_work.exponential(1.0 / cfg.rate)
                if t > cfg.sim_time:
                    break
                queues[s].append(self.new_tx(s, t))
        if "insert" in cfg.attack and cfg.adversaries:
            a = cfg.adversaries[0]
            targets = [y for s in range(cfg.n) if s not in self.adv_set for y in queues[s]]
            for y in targets:
                if self.rng_adv.random() < cfg.insert_prob:
                    queues[a].append(self.new_tx(a, y.t + cfg.d_obs, adv_tx=True, target=y))
            queues[a].sort(key=lambda x: x.t)
        return queues

    # ---------------------------------------------------------------- shards
    def shard_proc(self, s):
        cfg, env = self.cfg, self.env
        mult = cfg.slow_mult if s in self.slow_set else 1.0
        adv = s in self.adv_set
        queue, qi, pending = self.queues[s], 0, []
        h = 0
        while True:
            h += 1
            off = s * 0.001 if cfg.offset_mode == "id" else self.rng_off.uniform(0.0, cfg.eps)
            cut = h * cfg.block_interval * mult + off
            if cut > cfg.sim_time:
                return
            if cfg.halt_shard == s and cut >= cfg.halt_at:
                return
            yield env.timeout(cut - env.now)
            self.cut_hist[s].append(cut)

            if cfg.workload == "per_block":
                pending.extend(self.new_tx(s, cut) for _ in range(cfg.batch))
            else:
                while qi < len(queue) and queue[qi].t <= cut:
                    pending.append(queue[qi])
                    qi += 1

            if adv and "withhold" in cfg.attack and cfg.withhold_blocks > 0:
                d = cfg.withhold_blocks
                limit = self.cut_hist[s][h - d - 1] if h - d >= 1 else -math.inf
                include = [x for x in pending if x.adv_tx or x.t <= limit]
                for x in pending:
                    if not x.adv_tx:
                        x.withheld = True
                held = [x for x in pending if not (x.adv_tx or x.t <= limit)]
                pending = held
            else:
                include, pending = pending, []

            if adv and "reorder" in cfg.attack and include:
                # Leader observes the pending honest tx and front-runs them inside its block.
                include = [self.new_tx(s, cut, adv_tx=True)] + include

            ts = cut
            if adv and "skew" in cfg.attack and cfg.delta_max > 0:
                ts = cut - self.rng_skew.uniform(0.0, cfg.delta_max)
            for k, x in enumerate(include):
                x.B, x.T, x.cut, x.ts = h, k, cut, ts
            cl = CrossLink(s, h, ts, cut, include)
            d = sample_delay(self.rng_delay, cfg.delay_dist)
            if cfg.delay_target == s:
                d += cfg.delay_extra
            env.process(self.deliver(cl, d))

    def deliver(self, cl, d):
        yield self.env.timeout(d)
        cl.arrive = self.env.now
        self.beacon.receive(cl)

    def run(self):
        self.env.run(until=self.cfg.sim_time)
        return self


class BeaconBase:
    def __init__(self, sim):
        self.sim = sim
        self.env = sim.env
        self.cfg = sim.cfg
        self.out = []
        self.arr_evt = self.env.event()

    def emit(self, txs):
        now = self.env.now
        for x in txs:
            x.emit = now
            x.pos = len(self.out)
            self.out.append(x)

    def _signal(self):
        if not self.arr_evt.triggered:
            self.arr_evt.succeed()


class RoundBeacon(BeaconBase):
    """Algorithm 1: one round per height, closed by completeness or by t_r + tau_max."""

    def __init__(self, sim):
        super().__init__(sim)
        cfg = self.cfg
        self.present = defaultdict(set)    # height -> shards whose CrossLink has arrived
        self.unadmitted = []
        self.active = frozenset(range(cfg.n))
        self.rounds = []                   # (r, close_time, timed_out, first_shard, full)
        self._perm_cache = {}
        self.keyfn = self._make_key()
        self.env.process(self.run())

    def priority(self, r, s):
        cfg = self.cfg
        if cfg.priority == "static":
            return s
        if cfg.priority == "cyclic":
            return (s + r // cfg.epoch_len) % cfg.n
        if cfg.priority == "rotated":
            e = (r - 1) // cfg.epoch_len
            perm = self._perm_cache.get(e)
            if perm is None:
                perm = rotated_permutation(self.sim.seed, e, cfg.n)
                self._perm_cache[e] = perm
            return perm[s]
        raise ValueError(cfg.priority)

    def _make_key(self):
        cfg, prio = self.cfg, self.priority
        if cfg.engine == "haechi_round":
            return lambda x: (x.R, x.ts, x.shard, x.T)
        k = cfg.key
        if k == "RBST":
            return lambda x: (x.R, x.B, prio(x.R, x.shard), x.T)
        if k == "RBS":
            return lambda x: (x.R, x.B, prio(x.R, x.shard))
        if k == "RBT":
            return lambda x: (x.R, x.B, x.T, x.ts)
        if k == "RB":
            return lambda x: (x.R, x.B, x.ts)
        raise ValueError(k)

    def receive(self, cl):
        self.unadmitted.append(cl)
        self.present[cl.h].add(cl.s)
        self._signal()

    def complete(self, r):
        return self.present.get(r, set()) >= self.active

    def run(self):
        cfg, env = self.cfg, self.env
        r = 1
        while True:
            deadline = None if cfg.tau_max is None else r * cfg.block_interval + cfg.tau_max
            while not self.complete(r):
                if deadline is not None and env.now >= deadline:
                    break
                self.arr_evt = env.event()
                if deadline is None:
                    yield self.arr_evt
                else:
                    yield self.arr_evt | env.timeout(deadline - env.now)
            timed_out = not self.complete(r)
            admit = [cl for cl in self.unadmitted if cl.h <= r]
            self.unadmitted = [cl for cl in self.unadmitted if cl.h > r]
            txs = []
            for cl in admit:
                cl.R = r
                for x in cl.txs:
                    x.R = r
                    txs.append(x)
            txs.sort(key=self.keyfn)
            self.emit(txs)
            full = {cl.s for cl in admit if cl.h == r} >= self.active
            self.rounds.append((r, env.now, timed_out, txs[0].shard if txs else None, full))
            r += 1


class WatermarkBeacon(BeaconBase):
    """Haechi-style timestamp ordering without height alignment.

    A shard's watermark is the blockTS of its latest CrossLink received without gaps; a
    transaction is finalised once its blockTS is at most the minimum watermark over all
    shards, in (blockTS, S, T) order.
    """

    def __init__(self, sim):
        super().__init__(sim)
        n = self.cfg.n
        self.received = [dict() for _ in range(n)]
        self.contig = [0] * n
        self.wm = [-math.inf] * n
        self.pending = []
        self.rounds = []

    def receive(self, cl):
        s = cl.s
        self.received[s][cl.h] = cl
        while self.contig[s] + 1 in self.received[s]:
            self.contig[s] += 1
            c = self.received[s].pop(self.contig[s])
            self.wm[s] = c.ts
            self.pending.extend(c.txs)
        w = min(self.wm)
        if w == -math.inf or not self.pending:
            return
        self.pending.sort(key=lambda x: (x.ts, x.shard, x.T))
        k = 0
        while k < len(self.pending) and self.pending[k].ts <= w:
            k += 1
        if k:
            self.emit(self.pending[:k])
            self.pending = self.pending[k:]


def rotated_permutation(seed, epoch, n):
    """pi_e for epoch e: a uniformly random permutation derived from (seed, e)."""
    perm = np.random.default_rng([seed, 7919, epoch]).permutation(n)
    return [int(v) for v in perm]
