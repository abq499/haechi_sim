# sim/metrics.py
"""Fairness, latency and attack metrics computed from one simulation run."""
from collections import defaultdict

import numpy as np


def count_pairs_gt(a, w=None, gap=0.0):
    """Weighted count of pairs i < j with a[i] > a[j] + gap; pair (i, j) has weight w[j].

    Divide and conquer with sorted halves, O(N log^2 N).
    """
    a = np.asarray(a, dtype=float)
    w = np.ones(len(a)) if w is None else np.asarray(w, dtype=float)

    def rec(lo, hi):
        if hi - lo <= 64:
            seg, ws = a[lo:hi], w[lo:hi]
            m = np.triu(seg[:, None] > seg[None, :] + gap, 1)
            return float((m * ws[None, :]).sum()), np.sort(seg)
        mid = (lo + hi) // 2
        c1, left = rec(lo, mid)
        c2, right = rec(mid, hi)
        idx = np.searchsorted(left, a[mid:hi] + gap, side="right")
        c3 = float(((len(left) - idx) * w[mid:hi]).sum())
        return c1 + c2 + c3, np.sort(np.concatenate([left, right]), kind="mergesort")

    if len(a) < 2:
        return 0.0
    return rec(0, len(a))[0]


def _height_groups(txs):
    groups = defaultdict(list)
    for x in txs:
        groups[x.B].append(x)
    return groups.values()


def fvr_attack(txs, adv_set):
    """Paper Sec. 3: pairs (x adversarial shard, y honest) at the same height; violation when
    y was processed (block cut) before x but x is ordered first."""
    pairs = viol = 0
    for g in _height_groups(txs):
        adv = [x for x in g if x.shard in adv_set]
        hon = [y for y in g if y.shard not in adv_set]
        if not adv or not hon:
            continue
        pairs += len(adv) * len(hon)
        ac = np.array([x.cut for x in adv])
        ap = np.array([x.pos for x in adv])
        hc = np.array([y.cut for y in hon])
        hp = np.array([y.pos for y in hon])
        viol += int(((hc[None, :] < ac[:, None]) & (ap[:, None] < hp[None, :])).sum())
    return pairs, viol


def fvr_same_height(txs):
    """Old evaluation.calculate_fvr: all pairs at the same height, ordered earlier but cut later."""
    pairs = viol = 0
    for g in _height_groups(txs):
        g = sorted(g, key=lambda x: x.pos)
        k = len(g)
        pairs += k * (k - 1) // 2
        viol += int(count_pairs_gt([x.cut for x in g]))
    return pairs, viol


def frontrun_success(txs_by_pos):
    """Fraction of adversary-created tx that precede at least one honest tx created earlier."""
    n = len(txs_by_pos)
    suffix_min = np.full(n + 1, np.inf)
    for i in range(n - 1, -1, -1):
        x = txs_by_pos[i]
        v = x.t if not x.adv_tx else np.inf
        suffix_min[i] = min(suffix_min[i + 1], v)
    adv_idx = [i for i, x in enumerate(txs_by_pos) if x.adv_tx]
    if not adv_idx:
        return 0, float("nan")
    wins = sum(1 for i in adv_idx if suffix_min[i + 1] < txs_by_pos[i].t)
    return len(adv_idx), wins / len(adv_idx)


def overtakers(txs_by_pos, mask):
    """For each tx selected by mask: number of tx created later but ordered earlier."""
    t = np.array([x.t for x in txs_by_pos])
    order = np.argsort(t, kind="mergesort")
    rank = np.empty(len(t), dtype=int)
    rank[order] = np.arange(len(t))
    tree = np.zeros(len(t) + 1, dtype=np.int64)
    res = []
    for i, x in enumerate(txs_by_pos):
        r = rank[i]
        if mask[i]:
            # earlier-ordered tx with a strictly later creation time
            j, le = r + 1, 0
            while j > 0:
                le += tree[j]
                j -= j & -j
            res.append(i - le)
        j = r + 1
        while j <= len(t):
            tree[j] += 1
            j += j & -j
    return np.array(res)


def attack_induced(att, clean, adv_set):
    """Counterfactual effect of the timestamp lever: compare the attacked run with the same seed
    and delta_max = 0 (all other random streams identical).

    a_fvr: among same-height (adversarial x, honest y) pairs where y precedes x without the attack,
    the % that the attack flips. a_success: fraction of adversarial tx that overtake >= 1 honest tx
    because of the attack. a_gain: honest tx overtaken per adversarial tx (any height).
    """
    pos_c = {x.tid: x.pos for x in clean.beacon.out}
    out = [x for x in att.beacon.out if x.tid in pos_c]
    adv = [x for x in out if x.shard in adv_set]
    hon = [y for y in out if y.shard not in adv_set]
    if not adv or not hon:
        return {}
    hp_a = np.array([y.pos for y in hon])
    hp_c = np.array([pos_c[y.tid] for y in hon])
    hb = np.array([y.B for y in hon])
    flips = flips_same = base_same = gainers = 0
    for x in adv:
        before = hp_c < pos_c[x.tid]
        f = before & (hp_a > x.pos)
        same = hb == x.B
        n_f = int(f.sum())
        flips += n_f
        flips_same += int((f & same).sum())
        base_same += int((before & same).sum())
        gainers += n_f > 0
    return {
        "a_flips": flips, "a_flips_cross_height": flips - flips_same,
        "a_fvr": 100.0 * flips_same / base_same if base_same else float("nan"),
        "a_success": gainers / len(adv), "a_gain": flips / len(adv),
    }


INV_GAPS = (0.5, 1.0, 2.0, 3.0, 4.0)
SERIES_BINS = 10


def compute(sim):
    cfg = sim.cfg
    out = sim.beacon.out
    adv_set = sim.adv_set
    n_out = len(out)
    row = {
        "n_tx_created": len(sim.all_tx),
        "n_tx": n_out,
        "unfinalized": len(sim.all_tx) - n_out,
        "tps": n_out / cfg.sim_time,
    }
    if n_out == 0:
        return row

    lat = np.array([x.emit - x.cut for x in out])
    e2e = np.array([x.emit - x.t for x in out])
    row.update(
        lat_mean=float(lat.mean()), lat_p50=float(np.percentile(lat, 50)),
        lat_p99=float(np.percentile(lat, 99)),
        e2e_mean=float(e2e.mean()), e2e_p99=float(np.percentile(e2e, 99)),
    )

    p, v = fvr_attack(out, adv_set)
    row.update(n_pairs=p, n_viol_fvr=v, fvr=100.0 * v / p if p else float("nan"))
    p, v = fvr_same_height(out)
    row.update(n_pairs_sh=p, n_viol_sh=v, fvr_same_height=100.0 * v / p if p else float("nan"))

    cut = [x.cut for x in out]
    t = [x.t for x in out]
    all_pairs = n_out * (n_out - 1) / 2
    v_all = count_pairs_gt(cut)
    row.update(n_viol_allpairs=v_all, fvr_allpairs=100.0 * v_all / all_pairs if all_pairs else float("nan"))

    inv = count_pairs_gt(t)
    row.update(n_viol_ro=inv, ro_fvr=100.0 * inv / all_pairs if all_pairs else float("nan"),
               ro_inv_per_tx=inv / n_out)
    prefix_max = np.maximum.accumulate(np.array(t))
    gaps = prefix_max[:-1] - np.array(t[1:])
    row["max_inv_gap"] = float(max(gaps.max(), 0.0)) if len(gaps) else 0.0
    # Fraction of tx overtaken by at least one tx created later; cumulative gap histogram.
    row["ro_overtaken_frac"] = float((gaps > 0).sum() / n_out)
    for g in INV_GAPS:
        row[f"inv_gap_gt_{g}"] = count_pairs_gt(t, gap=g)
    # Mean latency per bin of block-cut time (shows backlog growth over the run).
    cuts = np.array(cut)
    bins = np.minimum((cuts / cfg.sim_time * SERIES_BINS).astype(int), SERIES_BINS - 1)
    series = [lat[bins == b].mean() if (bins == b).any() else float("nan") for b in range(SERIES_BINS)]
    row["lat_series"] = " ".join(f"{v:.3f}" for v in series)
    W = cfg.window()
    row["W"] = W
    if W is not None:
        honest_leader = np.array([0.0 if x.shard in adv_set else 1.0 for x in out])
        row["viol_out_W"] = count_pairs_gt(t, honest_leader, W)

    # Round statistics (round-based engines only).
    rounds = getattr(sim.beacon, "rounds", [])
    if rounds:
        row["rounds"] = len(rounds)
        row["skip_rate"] = sum(1 for r in rounds if r[2]) / len(rounds)
        full = [r[3] for r in rounds if r[4] and r[3] is not None]
        if full:
            wins = np.bincount(np.array(full), minlength=cfg.n) / len(full)
            row["win_rate_s0"] = float(wins[0])
            row["win_rate_max"] = float(wins.max())
            row["win_rates"] = " ".join(f"{w:.4f}" for w in wins)

    # Attack-specific metrics.
    if any(x.adv_tx for x in out):
        k, rate = frontrun_success(out)
        row.update(n_adv_tx=k, frontrun_rate=rate)
        tgt = [x for x in out if x.adv_tx and x.target is not None]
        done = [x for x in tgt if x.target.pos is not None]
        if done:
            row["insert_success"] = sum(1 for x in done if x.pos < x.target.pos) / len(done)
            row["n_insert"] = len(done)
    if "withhold" in cfg.attack and cfg.withhold_blocks >= 0 and adv_set:
        held = np.array([x.shard in adv_set and not x.adv_tx for x in out])
        if held.any():
            others = ~held
            row["withheld_e2e"] = float(e2e[held].mean())
            row["others_e2e"] = float(e2e[others].mean()) if others.any() else float("nan")
            ov = overtakers(out, held)
            row["withheld_overtakers"] = float(ov.mean())
            ov_o = overtakers(out, others)
            row["others_overtakers"] = float(ov_o.mean()) if len(ov_o) else float("nan")
    return row
