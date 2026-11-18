# configs/campaigns.py
"""Experiment campaigns. Each function yields SimConfig cells; every cell runs for all seeds.

A-D re-run the paper's campaigns with the old simulator's workload (one tx per block, shard
offset S_i ms, tx created at the block cut); they are kept as a control. The paper's main numbers
come from the lockstep model (E1_rofvr, E1_tail, R_*). E2-E7 are the experiments of todo-list B3-B8.
"""
from dataclasses import replace

from sim.config import SimConfig, TAU_UNIFORM

SEEDS = list(range(30))

LEGACY = SimConfig(workload="per_block", batch=1, offset_mode="id", delay_dist="uniform",
                   attack=("skew",))
# Lockstep model for the fairness experiments: Poisson clients, cut spread eps.
EPS = 0.05
LOCKSTEP = SimConfig(workload="poisson", rate=1.0, offset_mode="random", eps=EPS,
                     delay_dist="uniform", sim_time=300)

ENGINES_LEGACY = [dict(engine="haechi_round"), dict(engine="haechi"),
                  dict(engine="dlo", priority="static")]
ENGINES_FAIR = [dict(engine="haechi_round"), dict(engine="haechi"),
                dict(engine="dlo", priority="static"), dict(engine="dlo", priority="rotated")]


def last(n, k=1):
    return tuple(range(n - k, n))


def tau_thm2(delta):
    """Smallest tau_max allowed by Theorem 2: eps + tau + Delta."""
    return round(EPS + TAU_UNIFORM + delta, 4)


def A_skew():
    for dm in [0.1, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]:
        for e in ENGINES_LEGACY:
            yield replace(LEGACY, n=3, adversaries=last(3), delta_max=dm, sim_time=1000, **e)


def A_scale():
    for n in [3, 5, 10, 15, 20, 25, 30]:
        for e in ENGINES_LEGACY:
            yield replace(LEGACY, n=n, adversaries=last(n), delta_max=1.0, sim_time=500, **e)


def B_engines():
    for e in ENGINES_FAIR:
        yield replace(LEGACY, n=30, adversaries=last(30), delta_max=1.0, sim_time=500, **e)


def C_jitter():
    for dist in ["uniform", "lognormal", "pareto"]:
        for e in ENGINES_LEGACY:
            yield replace(LEGACY, n=10, adversaries=last(10), delta_max=1.0, delay_dist=dist,
                          sim_time=1000, **e)


def C_collusion():
    # 'low' reproduces experiments_collusion.py (attackers = first k shards).
    for k in [1, 2, 3]:
        for adv in [tuple(range(k)), last(10, k)]:
            for e in ENGINES_LEGACY:
                yield replace(LEGACY, n=10, adversaries=adv, delta_max=2.0, sim_time=500, **e)


def C_liveness():
    # experiments_liveness.py: n=5, attacker shard 0, last shard halts at t=30 s, 100 s run.
    for tau in [None, 0.5, 1.0, 2.0, 5.0]:
        for e in ENGINES_LEGACY:
            yield replace(LEGACY, n=5, adversaries=(0,), delta_max=1.0, halt_shard=4, halt_at=30.0,
                          tau_max=tau, sim_time=100, **e)


def D_ablation():
    for batch in [1, 4]:
        for key in ["RB", "RBT", "RBS", "RBST"]:
            yield replace(LEGACY, n=10, adversaries=last(10), delta_max=1.0, batch=batch,
                          engine="dlo", key=key, sim_time=500)


SKEWS = [0.1, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
SIZES = [3, 5, 10, 15, 20, 25, 30]


def E1_rofvr():  # todo B2 + main grid for Fig. 2 and tab:stats (lockstep model, uniform delay)
    for n in SIZES:
        for dm in SKEWS:
            for e in ENGINES_FAIR:
                yield replace(LOCKSTEP, n=n, adversaries=last(n), delta_max=dm,
                              tau_max=tau_thm2(dm), **e)


def E1_tail():  # todo B2 / C jitter: long-tail delays
    for n in [3, 10, 30]:
        for dm in [0.1, 1.0, 3.0]:
            for dist in ["lognormal", "pareto"]:
                for e in ENGINES_FAIR:
                    yield replace(LOCKSTEP, n=n, adversaries=last(n), delta_max=dm,
                                  delay_dist=dist, tau_max=tau_thm2(dm), **e)


def R_ablation():  # Campaign D on the lockstep model
    for key in ["RB", "RBT", "RBS", "RBST"]:
        yield replace(LOCKSTEP, n=10, adversaries=last(10), delta_max=1.0, tau_max=tau_thm2(1.0),
                      engine="dlo", key=key)
    yield replace(LOCKSTEP, n=10, adversaries=last(10), delta_max=1.0, tau_max=tau_thm2(1.0),
                  engine="dlo", priority="rotated")


def R_collusion():  # Campaign C collusion on the lockstep model, attackers low or high
    for k in [1, 2, 3]:
        for adv in [tuple(range(k)), last(10, k)]:
            for e in ENGINES_FAIR:
                yield replace(LOCKSTEP, n=10, adversaries=adv, delta_max=2.0,
                              tau_max=tau_thm2(2.0), **e)


def R_liveness():  # todo A6 on the lockstep model; adversary at the highest live identifier
    for tau in [None, 0.5, 1.0, 2.0, 5.0]:
        for e in ENGINES_FAIR:
            yield replace(LOCKSTEP, n=5, adversaries=(3,), delta_max=1.0, halt_shard=4,
                          halt_at=30.0, tau_max=tau, sim_time=100, **e)


def E2_reorder():  # todo B3
    for n, ks in [(10, [1, 2, 3]), (30, [1, 3, 6, 9])]:
        for k in ks:
            for e in [dict(engine="haechi_round"), dict(engine="dlo", priority="static"),
                      dict(engine="dlo", priority="rotated")]:
                yield replace(LOCKSTEP, n=n, adversaries=last(n, k), attack=("reorder",),
                              delta_max=0.0, tau_max=tau_thm2(0.0), **e)


def E3_insert():  # todo B4
    for pos in [0, 9]:
        for d in [0.01, 0.1, 0.5, 1.0, 2.0, 4.0]:
            for e in [dict(engine="haechi_round"), dict(engine="dlo", priority="static"),
                      dict(engine="dlo", priority="rotated")]:
                yield replace(LOCKSTEP, n=10, adversaries=(pos,), attack=("insert", "skew"),
                              delta_max=1.0, insert_prob=0.2, d_obs=d, tau_max=tau_thm2(1.0), **e)


def E4_withhold():  # todo B5
    for d in [0, 1, 2, 5]:
        for e in ENGINES_LEGACY:
            yield replace(LOCKSTEP, n=10, adversaries=(4,), attack=("withhold",), delta_max=0.0,
                          withhold_blocks=d, tau_max=tau_thm2(0.0), **e)


def E5_skip():  # todo B6: adversary delays the CrossLinks of honest shard 0 by D seconds
    for tau in [0.5, 1.0, 2.0, 5.0]:
        for D in [0.0, TAU_UNIFORM, 2 * TAU_UNIFORM, 5 * TAU_UNIFORM, 0.5, 1.0, 2.0, 5.0]:
            yield replace(LOCKSTEP, n=10, engine="dlo", priority="static", delta_max=0.0,
                          clock_tol=0.0, tau_max=tau, delay_target=0, delay_extra=D)


def E6_rotation():  # todo B7 (simulated; large horizons are computed in rotation_analytic.py)
    for n in [10, 20, 30]:
        for el in [1, 10, 100]:
            for prio in ["static", "cyclic", "rotated"]:
                yield replace(LEGACY, n=n, engine="dlo", priority=prio, epoch_len=el,
                              sim_time=1000)


def E7_hetero():  # todo B8
    for n in [10, 30]:
        slow = last(n, n // 5)
        for mult in [1, 2, 5, 10]:
            for e in [dict(engine="haechi"), dict(engine="haechi_round"),
                      dict(engine="dlo", priority="static"),
                      dict(engine="dlo", priority="static", tau_max=1.0)]:
                yield replace(LOCKSTEP, n=n, adversaries=(0,), delta_max=1.0, slow_shards=slow,
                              slow_mult=float(mult), sim_time=500, **e)


CAMPAIGNS = {f.__name__: f for f in [
    A_skew, A_scale, B_engines, C_jitter, C_collusion, C_liveness, D_ablation,
    E1_rofvr, E1_tail, R_ablation, R_collusion, R_liveness,
    E2_reorder, E3_insert, E4_withhold, E5_skip, E6_rotation, E7_hetero]}
