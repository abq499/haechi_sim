# DLO simulator

Discrete-event simulator, raw results and scripts for the paper

> **Deterministic Logical Ordering against Timestamp-Skew Front-Running in Sharded Blockchains** (ICCIES 2027)

The simulator compares two ways for a Beacon Chain to order cross-shard transactions:

- **Haechi-style** ordering by the block timestamp `blockTS` that each shard leader attaches. A Byzantine
  leader can skew its timestamp backwards within the clock-skew tolerance (the *Timestamp Skew Attack*).
- **DLO** (Deterministic Logical Ordering), which never reads `blockTS` and sorts by the key
  `(R, B, π_e(S), T)`: admission round, block height, epoch-rotated shard priority, index inside the block
  (Algorithm 1 of the paper).

Every number in the paper's tables and in Fig. 2 can be traced to a row of a CSV file in `results/`.

## Requirements

Python 3.13 (tested with 3.13.4). Pinned dependencies:

```bash
pip install -r requirements.txt
```

## Quick check

```bash
python -m unittest discover -s tests -v
```

The 13 tests check Lemma 1 (agreement, skew independence), Theorem 1, Theorem 2, the attack-induced FVR,
shard-priority rotation and the metric implementations (including a cross-check against the original
`legacy/evaluation.py`). They take about 10 s.

## Reproducing the results

```bash
python scripts/run_campaign.py --seeds 30          # all campaigns -> results/raw/<NAME>.csv, results/env.json
python scripts/run_campaign.py E1_rofvr --seeds 30 # a single campaign
python scripts/rotation_analytic.py                # long-horizon rotation -> results/raw/E6_rotation_analytic.csv
python scripts/sort_overhead.py                    # sort timing -> results/raw/E8_sort_overhead.csv (idle machine)
python scripts/summarize.py                        # results/raw -> results/summary/ (mean, SD, 95 % CI, tests)
python scripts/export_paper.py                     # results/raw -> results/paper/ (tables and Fig. 2 data)
```

A full run with 30 seeds takes about 10 minutes on 11 worker processes (`--workers N`); `E1_rofvr` alone
takes about 6 minutes. Pass `--out DIR` to write a trial run somewhere other than `results/`.
Each simulation component (workload, block-cut offsets, network delay, skew, adversary) draws from its own
random stream, so changing one parameter leaves the others identical for the same seed.

### Where each result in the paper comes from

The campaign letters in the paper (Table 3) map to the campaign functions in `configs/campaigns.py`:

| Paper | Campaign function(s) | Output in `results/paper/` |
|---|---|---|
| Fig. 2, Campaign A (skew, scale) | `E1_rofvr` | `fig_core_results_skew.csv`, `fig_core_results_scale.csv` |
| Table 4, Campaign B (engines, n = 30) | `E1_rofvr` | `tab_stats.csv` |
| Table 5, Campaign D (key ablation) | `R_ablation` | `tab_ablation.csv` |
| Table 6, Campaign C (robustness) | `E1_tail`, `R_collusion`, `E6_rotation` + `rotation_analytic.py`, `E7_hetero`, `R_liveness` | `tab_robust_*.csv` |
| Table 2, Campaign E (attacks) | `E2_reorder`, `E3_insert`, `E4_withhold`, `E5_skip` | `tab_attacks_*.csv` |
| Theorem 2 check | `E1_rofvr`, `E1_tail` | `thm2_check.csv` |
| Sort cost (Sec. 4, "Cost") | `scripts/sort_overhead.py` | `results/raw/E8_sort_overhead.csv` |

`results/paper/tables.md` collects all tables in one file. The campaigns `A_skew`, `A_scale`, `B_engines`,
`C_*` and `D_ablation` in `configs/campaigns.py` rerun the earlier workload model (one transaction per block,
honest order fixed by shard id) and are kept as a control; they are not used for the paper's numbers.

## Layout

```
sim/            simulator (SimPy)
  config.py     SimConfig: one frozen dataclass per experiment cell
  model.py      shards, network, RoundBeacon (DLO / Haechi-R), WatermarkBeacon (Haechi-W)
  metrics.py    attack-induced FVR, receive-order metrics, latency, attack metrics
  runner.py     run_one(config, seed) -> one CSV row
configs/        campaigns.py: the experiment grid
scripts/        run_campaign.py, summarize.py, export_paper.py, rotation_analytic.py, sort_overhead.py
tests/          unittest suite
results/        raw/ (one row per seed x cell), summary/, paper/, env.json (software and machine)
legacy/         the first simulator (simulation.py, evaluation.py, experiments_*.py); not used for the paper
```

Engines (`SimConfig.engine`): `dlo` (key `(R, B, π_e(S), T)`, other keys via `key` for the ablation),
`haechi_round` (Haechi-R: same rounds as DLO, key `(R, blockTS, S, T)`), and `haechi` (Haechi-W: timestamp
order with a per-shard watermark and no height alignment). Shard priority (`priority`): `static`, `cyclic`,
or `rotated` (random permutation per epoch).

## License

MIT, see [LICENSE](LICENSE).
