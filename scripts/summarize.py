# scripts/summarize.py
"""results/raw/*.csv -> results/summary/<campaign>.csv (mean, SD, 95% t-CI per cell) and
results/summary/tests.csv (DLO vs timestamp baselines: Mann-Whitney U, Bonferroni, Cliff's delta).
"""
import glob
import os
import sys
from dataclasses import fields

import numpy as np
import pandas as pd
from scipy import stats

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sim.config import SimConfig  # noqa: E402

CELL = [f.name for f in fields(SimConfig)] + ["engine_label", "k_adv"]
SKIP = {"seed", "wall_s", "win_rates", "campaign", "lat_series"}
TESTED = ["lat_mean", "a_fvr", "fvr", "ro_inv_per_tx"]


def cliffs_delta(a, b):
    a, b = np.asarray(a), np.asarray(b)
    if not len(a) or not len(b):
        return np.nan
    return float((np.sign(a[:, None] - b[None, :])).mean())


def summarize(df):
    cell = [c for c in CELL if c in df.columns]
    metrics = [c for c in df.columns if c not in cell and c not in SKIP
               and pd.api.types.is_numeric_dtype(df[c])]
    g = df.groupby(cell, dropna=False)
    cols = {"n_seeds": g.size()}
    for m in metrics:
        mean, sd, cnt = g[m].mean(), g[m].std(ddof=1), g[m].count()
        half = stats.t.ppf(0.975, np.maximum(cnt - 1, 1)) * sd / np.sqrt(cnt)
        cols[f"{m}_mean"], cols[f"{m}_sd"], cols[f"{m}_ci95"] = mean, sd, half.where(cnt > 1)
    return pd.concat(cols, axis=1).reset_index()


def tests(df, campaign):
    """Within each cell, compare every DLO variant against each timestamp baseline."""
    cell = [c for c in CELL if c in df.columns and c not in
            ("engine", "engine_label", "priority", "key", "tau_max")]
    rows = []
    for keys, grp in df.groupby(cell, dropna=False):
        labels = grp["engine_label"].unique()
        dlo = [l for l in labels if l.startswith("dlo")]
        base = [l for l in labels if l.startswith("haechi")]
        for d in dlo:
            for d_tau in grp.loc[grp.engine_label == d, "tau_max"].drop_duplicates():
                a_grp = grp[(grp.engine_label == d) & ((grp.tau_max == d_tau) |
                                                        (grp.tau_max.isna() & pd.isna(d_tau)))]
                for b in base:
                    b_grp = grp[grp.engine_label == b]
                    if pd.notna(d_tau) and (b_grp.tau_max == d_tau).any():
                        b_grp = b_grp[b_grp.tau_max == d_tau]
                    elif b_grp.tau_max.notna().any() and b_grp.tau_max.isna().any():
                        b_grp = b_grp[b_grp.tau_max.isna()]
                    for m in TESTED:
                        if m not in grp:
                            continue
                        a, bb = a_grp[m].dropna().values, b_grp[m].dropna().values
                        if len(a) < 2 or len(bb) < 2:
                            continue
                        if np.ptp(np.concatenate([a, bb])) == 0:
                            p = 1.0
                        else:
                            p = stats.mannwhitneyu(a, bb, alternative="two-sided").pvalue
                        rows.append(dict(zip(cell, keys if isinstance(keys, tuple) else (keys,)),
                                         campaign=campaign, dlo=d, dlo_tau_max=d_tau, baseline=b,
                                         metric=m, dlo_mean=a.mean(), base_mean=bb.mean(),
                                         p=p, cliffs_delta=cliffs_delta(a, bb)))
    t = pd.DataFrame(rows)
    if len(t):
        for m in TESTED:
            sel = t.metric == m
            t.loc[sel, "p_bonf"] = np.minimum(t.loc[sel, "p"] * sel.sum(), 1.0)
    return t


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "results")
    raw = os.path.join(base, "raw")
    out = os.path.join(base, "summary")
    os.makedirs(out, exist_ok=True)
    all_tests = []
    for path in sorted(glob.glob(os.path.join(raw, "*.csv"))):
        name = os.path.splitext(os.path.basename(path))[0]
        df = pd.read_csv(path)
        if "engine_label" not in df.columns:
            continue
        summarize(df).to_csv(os.path.join(out, f"{name}.csv"), index=False)
        all_tests.append(tests(df, name))
        print("summarised", name)
    pd.concat(all_tests, ignore_index=True).to_csv(os.path.join(out, "tests.csv"), index=False)


if __name__ == "__main__":
    main()
