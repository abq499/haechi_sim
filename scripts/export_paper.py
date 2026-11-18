# scripts/export_paper.py
"""results/raw -> results/paper/: Fig. 2 data (same columns as the paper's figures/*.csv plus
95 % CI columns) and every table the revision needs, as CSV plus one tables.md for review.

Attack comparisons use haechi_round (same rounds, key differs only); latency/availability also
report the watermark Haechi.
"""
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "results")
RAW = os.path.join(BASE, "raw")
OUT = os.path.join(BASE, "paper")
ENG = {"haechi_round": "haechi", "haechi": "haechiwm", "dlo-static": "dlo", "dlo-rotated": "dlorot"}


def raw(name):
    return pd.read_csv(os.path.join(RAW, f"{name}.csv"))


def ci95(v):
    v = np.asarray(v, dtype=float)
    v = v[~np.isnan(v)]
    if len(v) < 2:
        return np.nan
    return float(stats.t.ppf(0.975, len(v) - 1) * v.std(ddof=1) / np.sqrt(len(v)))


def agg(df, by, metrics):
    g = df.groupby(by, dropna=False)
    parts = {}
    for m in metrics:
        parts[m] = g[m].mean()
        parts[f"{m}_sd"] = g[m].std(ddof=1)
        parts[f"{m}_ci"] = g[m].apply(ci95)
    res = pd.concat(parts, axis=1)
    res["seeds"] = g.size()
    return res.reset_index()


def md_table(df):
    """Markdown table without the optional tabulate dependency."""
    named = isinstance(df.index, pd.MultiIndex) or df.index.name is not None
    df = df.reset_index() if named else df.reset_index(drop=True)
    cols = [str(c) for c in df.columns]
    fmt = lambda v: "–" if (isinstance(v, float) and np.isnan(v)) else str(v)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(fmt(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines)


def pm(mean, sd, digits=3):
    if pd.isna(mean):
        return "–"
    return f"{mean:.{digits}f} ± {sd:.{digits}f}" if not pd.isna(sd) else f"{mean:.{digits}f}"


def wide(df, index, metrics):
    """One row per index value, columns <metric>_<engine> and <metric>_<engine>_ci."""
    df = df[df.engine_label.isin(ENG)].copy()
    df["eng"] = df.engine_label.map(ENG)
    a = agg(df, [index, "eng"], metrics)
    cols = {}
    for m in metrics:
        cols[m] = a.pivot(index=index, columns="eng", values=m).add_prefix(f"{m}_")
        cols[m + "ci"] = a.pivot(index=index, columns="eng", values=f"{m}_ci").add_prefix(f"{m}_").add_suffix("_ci")
    return pd.concat(cols.values(), axis=1).reset_index()


def mw(a, b):
    a, b = np.asarray(a), np.asarray(b)
    if np.ptp(np.concatenate([a, b])) == 0:
        return 1.0, 0.0
    p = stats.mannwhitneyu(a, b, alternative="two-sided").pvalue
    return p, float(np.sign(a[:, None] - b[None, :]).mean())


def main():
    os.makedirs(OUT, exist_ok=True)
    md = ["# Số liệu cho bản sửa (tự sinh bởi scripts/export_paper.py)\n",
          "Mean ± SD trên 30 seed; CI là nửa độ rộng khoảng tin cậy 95 % (Student t).\n"]

    # ---------------------------------------------------------------- Fig. 2
    e1 = raw("E1_rofvr")
    skew = e1[e1.n == 3].rename(columns={"delta_max": "skew"})
    s = wide(skew, "skew", ["a_fvr", "lat_mean"]).rename(columns=lambda c: c.replace("a_fvr", "fvr").replace("lat_mean", "lat"))
    s.to_csv(os.path.join(OUT, "fig_core_results_skew.csv"), index=False, float_format="%.4f")
    scale = e1[e1.delta_max == 1.0]
    c = wide(scale, "n", ["tps", "lat_mean", "a_fvr"]).rename(columns=lambda c: c.replace("lat_mean", "lat").replace("a_fvr", "fvr"))
    c.to_csv(os.path.join(OUT, "fig_core_results_scale.csv"), index=False, float_format="%.4f")
    md += ["## Fig. 2 (E1_rofvr, uniform delay)\n", "(a, b) n = 3, theo δ_max:\n",
           s[["skew", "fvr_haechi", "fvr_haechiwm", "fvr_dlo", "fvr_dlorot", "lat_haechi", "lat_haechiwm", "lat_dlo"]].round(4).pipe(md_table),
           "\n(c, d) δ_max = 1.0 s, theo n:\n",
           c[["n", "tps_haechi", "tps_dlo", "lat_haechi", "lat_haechiwm", "lat_dlo", "fvr_haechi", "fvr_dlo"]].round(4).pipe(md_table), "\n"]

    # ---------------------------------------------------------------- tab:stats (n = 30)
    b = e1[(e1.n == 30) & (e1.delta_max == 1.0)]
    metrics = ["a_fvr", "a_success", "ro_inv_per_tx", "ro_overtaken_frac", "lat_mean", "lat_p99", "tps"]
    t = agg(b, ["engine_label"], metrics)
    t.to_csv(os.path.join(OUT, "tab_stats.csv"), index=False)
    rows = []
    for _, r in t.iterrows():
        rows.append({"engine": r.engine_label, "A-FVR (%)": pm(r.a_fvr, r.a_fvr_sd, 2), "A-FVR CI": f"±{r.a_fvr_ci:.2f}",
                     "attack success": pm(r.a_success, r.a_success_sd, 3),
                     "overtaken/tx": pm(r.ro_inv_per_tx, r.ro_inv_per_tx_sd, 2),
                     "% tx overtaken": pm(100 * r.ro_overtaken_frac, 100 * r.ro_overtaken_frac_sd, 1),
                     "latency (s)": pm(r.lat_mean, r.lat_mean_sd, 4), "lat CI": f"±{r.lat_mean_ci:.4f}",
                     "p99 (s)": pm(r.lat_p99, r.lat_p99_sd, 3)})
    tests = []
    for d in ["dlo-static", "dlo-rotated"]:
        for base in ["haechi_round", "haechi"]:
            for m in ["lat_mean", "a_fvr", "ro_inv_per_tx"]:
                p, cd = mw(b[b.engine_label == d][m], b[b.engine_label == base][m])
                tests.append({"DLO": d, "baseline": base, "metric": m, "p (MW)": f"{p:.2e}",
                              "p Bonferroni (×12)": f"{min(1, 12 * p):.2e}", "Cliff δ": round(cd, 3)})
    md += ["## tab:stats — n = 30, δ_max = 1.0 s (E1_rofvr)\n", pd.DataFrame(rows).pipe(md_table),
           "\nKiểm định Mann–Whitney U hai phía, Bonferroni trên 12 phép so sánh:\n", pd.DataFrame(tests).pipe(md_table), "\n"]

    # ---------------------------------------------------------------- ablation
    ab = raw("R_ablation")
    a = agg(ab, ["engine_label"], ["a_fvr", "fvr", "ro_inv_per_tx"])
    a.to_csv(os.path.join(OUT, "tab_ablation.csv"), index=False)
    md += ["## tab:ablation — n = 10, δ_max = 1.0 s (R_ablation)\n",
           pd.DataFrame([{"key": r.engine_label, "A-FVR (%)": pm(r.a_fvr, r.a_fvr_sd, 2), "FVR §3 cũ (%)": pm(r.fvr, r.fvr_sd, 2),
                          "overtaken/tx": pm(r.ro_inv_per_tx, r.ro_inv_per_tx_sd, 2)} for _, r in a.iterrows()]).pipe(md_table), "\n"]

    # ---------------------------------------------------------------- robustness
    tail = pd.concat([e1[(e1.n == 10) & (e1.delta_max == 1.0)], raw("E1_tail").query("n == 10 and delta_max == 1.0")])
    j = agg(tail, ["delay_dist", "engine_label"], ["a_fvr", "lat_p99", "skip_rate"])
    j.to_csv(os.path.join(OUT, "tab_robust_delay.csv"), index=False)
    col = agg(raw("R_collusion"), ["adversaries", "engine_label"], ["a_fvr"])
    col.to_csv(os.path.join(OUT, "tab_robust_collusion.csv"), index=False)
    rot = pd.read_csv(os.path.join(RAW, "E6_rotation_analytic.csv"))
    r = agg(rot, ["n", "epochs", "policy"], ["win_rate_s0", "win_rate_max", "chi2_p"])
    r.to_csv(os.path.join(OUT, "tab_robust_rotation.csv"), index=False)
    het = agg(raw("E7_hetero"), ["n", "slow_mult", "engine_label", "tau_max"], ["lat_mean", "lat_p99", "tps", "unfinalized"])
    het.to_csv(os.path.join(OUT, "tab_robust_hetero.csv"), index=False)
    liv = agg(raw("R_liveness"), ["tau_max", "engine_label"], ["n_tx", "a_fvr", "skip_rate"])
    liv.to_csv(os.path.join(OUT, "tab_robust_liveness.csv"), index=False)
    md += ["## tab:robust\n", "Trễ đuôi dài (n = 10, δ = 1.0):\n",
           j[["delay_dist", "engine_label", "a_fvr", "lat_p99", "lat_p99_sd", "skip_rate"]].round(3).pipe(md_table),
           "\nCollusion (n = 10, δ = 2.0; adversaries = ID của shard đối thủ):\n",
           col[["adversaries", "engine_label", "a_fvr", "a_fvr_sd"]].round(2).pipe(md_table),
           "\nRotation (tính từ bộ sinh hoán vị; win rate của shard 0, fair share = 1/n):\n",
           r[r.policy != "cyclic"][["n", "epochs", "policy", "win_rate_s0", "win_rate_s0_sd", "win_rate_max", "chi2_p"]].round(4).pipe(md_table),
           "\nTải không đồng nhất (20 % shard chậm, 500 s):\n",
           het[["n", "slow_mult", "engine_label", "tau_max", "lat_mean", "lat_p99", "tps", "unfinalized"]].round(3).pipe(md_table),
           "\nLiveness (n = 5, shard 4 dừng ở t = 30 s, cửa sổ 100 s):\n",
           liv[["tau_max", "engine_label", "n_tx", "n_tx_sd", "a_fvr", "skip_rate"]].round(3).pipe(md_table), "\n"]

    # ---------------------------------------------------------------- attacks (tab:attacks "Measured")
    e2 = agg(raw("E2_reorder"), ["n", "k_adv", "engine_label"], ["frontrun_rate", "ro_inv_per_tx"])
    e3 = agg(raw("E3_insert"), ["adversaries", "engine_label", "d_obs"], ["insert_success"])
    e4 = agg(raw("E4_withhold"), ["withhold_blocks", "engine_label"], ["withheld_e2e", "others_e2e", "withheld_overtakers", "others_overtakers"])
    e5r = raw("E5_skip")
    e5r["viol_run"] = (e5r.viol_out_W > 0).astype(float)
    e5r["thm2_holds"] = e5r.tau_max >= 0.1 + e5r.delay_extra
    e5 = agg(e5r, ["tau_max", "delay_extra"], ["skip_rate", "viol_run", "viol_out_W", "max_inv_gap", "lat_mean"])
    for name, df in [("tab_attacks_reorder", e2), ("tab_attacks_insert", e3), ("tab_attacks_withhold", e4), ("tab_attacks_skip", e5)]:
        df.to_csv(os.path.join(OUT, f"{name}.csv"), index=False)
    md += ["## tab:attacks — số đo\n", "E2 reorder trong block:\n",
           e2[["n", "k_adv", "engine_label", "frontrun_rate", "ro_inv_per_tx"]].round(3).pipe(md_table),
           "\nE3 chèn sau khi quan sát (tỉ lệ x đứng trước y):\n",
           e3.pivot_table(index=["adversaries", "engine_label"], columns="d_obs", values="insert_success").round(3).pipe(md_table),
           "\nE4 withholding:\n", e4.round(3).drop(columns=[c for c in e4.columns if c.endswith("_ci")]).pipe(md_table),
           "\nE5 forced skip (trễ thêm D trên CrossLink của shard 0; viol_run = tỉ lệ lần chạy có vi phạm ngoài W):\n",
           e5[["tau_max", "delay_extra", "skip_rate", "viol_run", "max_inv_gap", "lat_mean"]].round(3).pipe(md_table), "\n"]

    # ---------------------------------------------------------------- Theorem 2 check
    th = pd.concat([e1, raw("E1_tail")])
    th = th[th.engine_label.str.startswith("dlo") | (th.engine_label == "haechi_round")]
    thm = th.groupby(["delay_dist", "engine_label"]).agg(runs=("seed", "size"), runs_with_viol=("viol_out_W", lambda v: int((v > 0).sum())),
                                                          max_gap_minus_W=("max_inv_gap", "max"))
    thm["max_gap_minus_W"] = th.assign(d=th.max_inv_gap - th.W).groupby(["delay_dist", "engine_label"]).d.max()
    thm.to_csv(os.path.join(OUT, "thm2_check.csv"))
    gaps = th[th.delay_dist == "uniform"].groupby("engine_label")[[f"inv_gap_gt_{g}" for g in (0.5, 1.0, 2.0, 3.0, 4.0)] + ["n_viol_ro"]].sum()
    md += ["## Kiểm chứng Định lý 2 (E1_rofvr + E1_tail)\n", thm.reset_index().round(3).pipe(md_table),
           "\nHistogram tích lũy độ lệch t(x) − t(y) của các cặp bị đảo (uniform, tổng trên mọi lần chạy):\n",
           gaps.reset_index().pipe(md_table), "\n"]

    with open(os.path.join(OUT, "tables.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
