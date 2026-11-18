# sim/config.py
from dataclasses import dataclass, asdict
from typing import Optional, Tuple

# Upper bound of the uniform delay distribution, used as the post-GST bound tau.
TAU_UNIFORM = 0.05


@dataclass(frozen=True)
class SimConfig:
    n: int = 10
    # Beacon ordering engine:
    #   'dlo'          : rounds + key (R, B, pi_e(S), T)            (Algorithm 1)
    #   'haechi'       : timestamp order with a per-shard watermark, no height alignment
    #   'haechi_round' : same rounds as DLO, key (R, blockTS, S, T)  (model of the old simulator)
    engine: str = "dlo"
    # DLO key ablation: 'RBST' (full), 'RBS', 'RBT', 'RB'. Keys without S break ties by blockTS.
    key: str = "RBST"
    # Shard priority pi_e: 'static' (identity), 'cyclic' ((S + epoch) % n, old simulator),
    # 'rotated' (uniformly random permutation per epoch).
    priority: str = "static"
    epoch_len: int = 100

    block_interval: float = 2.0          # lambda
    sim_time: float = 500.0
    # Block cut offset inside a height: 'id' -> S_i ms (old simulator), 'random' -> U(0, eps).
    offset_mode: str = "id"
    eps: float = 0.0
    delay_dist: str = "uniform"          # 'uniform' | 'lognormal' | 'pareto'

    # Workload: 'per_block' -> `batch` tx created at each block cut (old simulator);
    #           'poisson'   -> clients submit tx at `rate` tx/s per shard.
    workload: str = "per_block"
    batch: int = 1
    rate: float = 1.0

    # Adversary: shards whose leaders are Byzantine, and which levers they use.
    adversaries: Tuple[int, ...] = ()
    attack: Tuple[str, ...] = ("skew",)  # subset of: skew, reorder, insert, withhold
    delta_max: float = 0.0               # max timestamp rewind (A1)
    insert_prob: float = 0.0             # insert: fraction of honest tx targeted
    d_obs: float = 0.0                   # insert: observation delay
    withhold_blocks: int = 0             # withhold: extra heights a tx is held back

    tau_max: Optional[float] = None      # round timeout, anchored at t_r = r * lambda
    slow_shards: Tuple[int, ...] = ()
    slow_mult: float = 1.0
    halt_shard: Optional[int] = None
    halt_at: Optional[float] = None
    delay_target: Optional[int] = None   # A3: extra network delay on this shard's CrossLinks
    delay_extra: float = 0.0

    # Clock tolerance Delta used for the fairness window W = lambda + tau_max + Delta.
    # None -> Delta = delta_max.
    clock_tol: Optional[float] = None

    def engine_label(self) -> str:
        if self.engine == "dlo":
            label = f"dlo-{self.priority}"
            return label if self.key == "RBST" else f"{label}-{self.key}"
        return self.engine

    def window(self) -> Optional[float]:
        """W of Theorem 2, or None when no timeout is configured."""
        if self.tau_max is None:
            return None
        tol = self.delta_max if self.clock_tol is None else self.clock_tol
        return self.block_interval + self.tau_max + tol

    def as_row(self) -> dict:
        row = asdict(self)
        for k in ("adversaries", "attack", "slow_shards"):
            row[k] = " ".join(str(v) for v in row[k])
        row["k_adv"] = len(self.adversaries)
        row["engine_label"] = self.engine_label()
        return row
