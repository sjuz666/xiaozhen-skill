"""
Robustness, leave-one-chain-out CV, and convergence-rate checks on Carr,
Smith, Cornish & Kirby (2017) real data. Companion to real_data_analysis.py.

Three analyses:
  R1) Robustness grid. Vary embedding dim d in {3,5,7,10}, burn-in in {2,3,4,5},
      anchors in {20,40,60}. Report how V*_pred / V*_emp and relative error
      shift across the grid. Goal: show that the main claim is not
      sensitive to a single pipeline choice.
  R2) Leave-one-chain-out (LOCO) cross validation. For each held-out chain,
      estimate A, sigma^2 on the other three chains; predict V* from those
      estimates; compare to empirical V* on the held-out chain.
      Goal: demonstrate out-of-sample generalization.
  R3) Convergence rate on real data. Fit log(V_n - V*_pred) against n for
      generations in the transient regime and compare the slope to the
      theoretical value 2*log(lambda_bar). Goal: check the second
      qualitative prediction of Theorem 3.1 beyond just V*.
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import json
import itertools

import sys
sys.path.insert(0, "/sessions/vigilant-gracious-noether/mnt/meme传播理论论文")
from real_data_analysis import (
    load_experiment, build_embedding, estimate, align_trajectories,
    CHAINS_BY_EXP, N_GEN
)

OUT = "/sessions/vigilant-gracious-noether/mnt/meme传播理论论文"


def pipeline(data, dim, burn_in, n_anchors, seed, held_out_chain=None):
    """Run the full pipeline on `data` (dict chain -> list of generations).
    If held_out_chain is provided, estimate on all chains except it and
    evaluate V_emp on the held-out chain only.
    Returns (lam2, sigma2, V_pred, V_emp, gen_V_train, gen_V_heldout)
    """
    all_signals = []
    for chain, gens in data.items():
        for rows in gens:
            if rows is None:
                continue
            for sig, _ in rows:
                all_signals.append(sig)
    sig_to_vec, _ = build_embedding(all_signals, n_anchors=n_anchors,
                                    dim=dim, seed=seed)

    pairs_train = []
    gen_vecs_train = [[] for _ in range(N_GEN + 1)]
    gen_vecs_heldout = [[] for _ in range(N_GEN + 1)]

    for chain, gens in data.items():
        trajectories = align_trajectories(gens)
        for k, traj in trajectories.items():
            vecs = [sig_to_vec[s] for s in traj]
            target_gens = (gen_vecs_heldout if chain == held_out_chain
                           else gen_vecs_train)
            for g, v in enumerate(vecs):
                target_gens[g].append(v)
            if chain == held_out_chain:
                continue
            for n in range(burn_in, N_GEN):
                pairs_train.append((vecs[n], vecs[n + 1]))

    A_hat, sigma2, lam2, mu_y = estimate(pairs_train, dim)
    V_pred = sigma2 / (1 - lam2) if lam2 < 1 else float("inf")

    # Empirical V*: use held-out chain's last 3 gens if present, otherwise all.
    gen_vecs_for_emp = gen_vecs_heldout if held_out_chain else gen_vecs_train
    tail = []
    for g in range(N_GEN - 2, N_GEN + 1):
        vs = np.array(gen_vecs_for_emp[g])
        if len(vs) == 0:
            continue
        tail.extend(list(vs - mu_y))
    tail = np.array(tail)
    V_emp = np.mean(np.sum(tail ** 2, axis=1)) if len(tail) else float("nan")

    # Per-generation V_n on the training chains (for convergence rate)
    gen_V_train = []
    for g in range(N_GEN + 1):
        vs = np.array(gen_vecs_train[g])
        if len(vs) == 0:
            gen_V_train.append(float("nan"))
        else:
            gen_V_train.append(float(np.mean(np.sum((vs - mu_y) ** 2, axis=1))))

    return {
        "lam2": float(lam2),
        "sigma2": float(sigma2),
        "V_pred": float(V_pred),
        "V_emp": float(V_emp),
        "gen_V_train": gen_V_train,
    }


def run_R1_robustness(exp_num):
    print("=" * 70)
    print(f"R1. Robustness grid for Experiment {exp_num}")
    print("=" * 70)
    data = load_experiment(exp_num)
    grid = list(itertools.product(
        [3, 5, 7, 10],      # dim
        [2, 3, 4, 5],       # burn_in
        [20, 40, 60],       # anchors
    ))
    rows = []
    for dim, b, na in grid:
        # Average over 5 anchor seeds per cell
        preds, emps, lams, sigs = [], [], [], []
        for seed in range(5):
            r = pipeline(data, dim=dim, burn_in=b, n_anchors=na, seed=seed)
            preds.append(r["V_pred"]); emps.append(r["V_emp"])
            lams.append(r["lam2"]); sigs.append(r["sigma2"])
        preds = np.array(preds); emps = np.array(emps)
        lams = np.array(lams); sigs = np.array(sigs)
        rel = np.abs(preds - emps) / emps
        ratio = preds / emps
        rows.append({
            "dim": dim, "burn_in": b, "n_anchors": na,
            "lam2_mean": float(lams.mean()),
            "sigma2_mean": float(sigs.mean()),
            "V_pred_mean": float(preds.mean()),
            "V_emp_mean": float(emps.mean()),
            "rel_err_pct_mean": float(rel.mean() * 100),
            "ratio_mean": float(ratio.mean()),
            "ratio_sd": float(ratio.std()),
        })
        print(f"  d={dim}, burn={b}, anchors={na}: "
              f"lam2={lams.mean():.3f} sigma2={sigs.mean():.2f} "
              f"V_pred={preds.mean():.2f} V_emp={emps.mean():.2f} "
              f"rel.err={rel.mean()*100:.1f}% ratio={ratio.mean():.2f}")
    return rows


def run_R2_loco(exp_num):
    print()
    print("=" * 70)
    print(f"R2. Leave-one-chain-out cross validation, Experiment {exp_num}")
    print("=" * 70)
    data = load_experiment(exp_num)
    chains = list(data.keys())
    results = []
    for held in chains:
        # Average over 5 anchor seeds
        preds, emps, lams, sigs = [], [], [], []
        for seed in range(5):
            r = pipeline(data, dim=5, burn_in=3, n_anchors=40,
                         seed=seed, held_out_chain=held)
            preds.append(r["V_pred"]); emps.append(r["V_emp"])
            lams.append(r["lam2"]); sigs.append(r["sigma2"])
        preds = np.array(preds); emps = np.array(emps)
        lams = np.array(lams); sigs = np.array(sigs)
        rel = np.abs(preds - emps) / emps
        print(f"  held-out chain {held}: "
              f"lam2={lams.mean():.3f} sigma2={sigs.mean():.2f} "
              f"V_pred={preds.mean():.2f} V_emp_heldout={emps.mean():.2f} "
              f"rel.err={rel.mean()*100:.1f}%")
        results.append({
            "held_out": held,
            "lam2_mean": float(lams.mean()),
            "sigma2_mean": float(sigs.mean()),
            "V_pred_mean": float(preds.mean()),
            "V_emp_mean": float(emps.mean()),
            "rel_err_pct_mean": float(rel.mean() * 100),
        })
    return results


def run_R3_convergence_rate(exp_num):
    print()
    print("=" * 70)
    print(f"R3. Convergence rate on real data, Experiment {exp_num}")
    print("=" * 70)
    data = load_experiment(exp_num)
    # Aggregate across seeds to smooth V_n trajectory
    all_gen_V = []
    all_lam2 = []
    all_V_pred = []
    for seed in range(10):
        r = pipeline(data, dim=5, burn_in=3, n_anchors=40, seed=seed)
        all_gen_V.append(r["gen_V_train"])
        all_lam2.append(r["lam2"])
        all_V_pred.append(r["V_pred"])
    V_n = np.mean(all_gen_V, axis=0)  # average V_n across seeds
    V_star = np.mean(all_V_pred)
    lam2 = np.mean(all_lam2)
    theoretical_slope = np.log(lam2)  # one-step decay = lam^2 per gen so slope of log|V_n - V*| vs n is log(lam^2)=2*log(lam)
    print(f"  Mean V_n across 10 seeds: {[round(v,2) for v in V_n]}")
    print(f"  Mean V*_pred: {V_star:.3f}")
    print(f"  Mean lambda_bar^2: {lam2:.3f}")
    print(f"  Theoretical slope (log of lambda_bar^2): {theoretical_slope:.3f}")
    # V_n - V* converges as lam^{2n}, so log|V_n - V*| vs n should have slope log(lam^2) = 2 log(lam)
    deviation = V_n - V_star
    signs = np.sign(deviation)
    print(f"  Sign of (V_n - V*): {[int(s) for s in signs]}")
    # Fit linear regression only on non-nan, non-zero deviations
    good = (~np.isnan(deviation)) & (np.abs(deviation) > 1e-6)
    n_arr = np.arange(N_GEN + 1)[good]
    log_dev = np.log(np.abs(deviation[good]))
    if len(n_arr) >= 3:
        slope, intercept = np.polyfit(n_arr, log_dev, 1)
        print(f"  Empirical slope: {slope:.3f}")
        print(f"  Theoretical slope: {theoretical_slope:.3f}")
        print(f"  Ratio empirical/theoretical: {slope/theoretical_slope:.3f}")
    else:
        slope = float("nan")
        intercept = float("nan")

    # Plot
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(range(N_GEN + 1), V_n, "bo-", label=r"$V_n$ (empirical, mean over 10 seeds)")
    ax.axhline(y=V_star, color="r", linestyle="--",
               label=fr"$V^*$ predicted = {V_star:.2f}")
    ax.set_xlabel("Generation $n$", fontsize=12)
    ax.set_ylabel(r"$V_n$", fontsize=12)
    ax.set_title(f"Experiment {exp_num}: $V_n$ trajectory (real data)", fontsize=12)
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT, f"real_data_convergence_exp{exp_num}.png"), dpi=300)
    print(f"  Saved real_data_convergence_exp{exp_num}.png")

    return {
        "V_n": V_n.tolist(),
        "V_star": float(V_star),
        "lam2": float(lam2),
        "theoretical_slope": float(theoretical_slope),
        "empirical_slope": float(slope) if not np.isnan(slope) else None,
        "ratio": float(slope / theoretical_slope) if (not np.isnan(slope) and theoretical_slope != 0) else None,
    }


if __name__ == "__main__":
    out = {"R1": {}, "R2": {}, "R3": {}}
    for exp in [1, 2]:
        out["R1"][exp] = run_R1_robustness(exp)
    for exp in [1, 2]:
        out["R2"][exp] = run_R2_loco(exp)
    for exp in [1, 2]:
        out["R3"][exp] = run_R3_convergence_rate(exp)
    with open(os.path.join(OUT, "real_data_robustness.json"), "w") as f:
        json.dump(out, f, indent=2)
    print()
    print("Saved real_data_robustness.json")
