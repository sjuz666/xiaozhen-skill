"""
Real-data validation of Theorem 3.1 on iterated learning data from
Carr, Smith, Cornish & Kirby (2017, Cognitive Science), the direct
lab-successor of Kirby, Cornish & Smith (2008, PNAS).

Data source: https://github.com/jwcarr/flatlanders
  - 3 experiments, 4 chains each (A, B, C, D), 10 generations per chain
  - Each generation's "static set" contains 48 triangle stimuli with fixed
    coordinates (3 vertices x 2 coords = 6-dim continuous meaning vector)
  - Participant produces a string signal for each triangle
  - Experiment 1: free iterated learning
  - Experiment 2: iterated learning with duplicate-filtering (this is the
    condition that matches Kirby 2008 Experiment 2)
  - Experiment 3: communication game (we exclude this - different dynamics)

Pipeline for each experiment:
  (1) Parse static-set files per chain per generation -> (meaning, signal)
  (2) Build Levenshtein-distance embedding of all signals using shared
      anchor set across all chains and generations
  (3) For each meaning i, get trajectory x_i^{(0)} .. x_i^{(10)} in R^d
  (4) Build pairs (x^{(n)}, x^{(n+1)}) with burn_in=3
  (5) OLS: estimate A_hat, sigma^2_hat
  (6) lambda_bar^2 = tr(A A^T)/d
  (7) V*_pred = sigma^2_hat / (1 - lambda_bar^2)
  (8) V*_emp  = mean ||x - mu||^2 over last 3 generations
  (9) compare
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import json

REPO = "/sessions/vigilant-gracious-noether/flatlanders_repo"
OUT = "/sessions/vigilant-gracious-noether/mnt/meme传播理论论文"

CHAINS_BY_EXP = {
    1: ["A", "B", "C", "D"],
    2: ["E", "F", "G", "H"],
    3: ["I", "J", "K", "L"],
}
N_GEN = 10  # generations 0..10 inclusive

# ------------------------------------------------------------
# Parsing
# ------------------------------------------------------------

def parse_static_file(path):
    """
    Return a list of (signal, triangle_vec) in row order.
    Handles both gen-0 format (leading index) and gen>=1 format (trailing
    timestamp + order). The signal is identified as the first field that
    is NOT a pure integer and does NOT contain a comma (so it's not a
    vertex coord).
    """
    rows = []
    with open(path) as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 4:
                continue
            # Find the signal: first non-pure-integer, non-comma-containing field
            sig = None
            sig_idx = None
            for j, p in enumerate(parts):
                if "," in p:
                    continue
                if p.strip().isdigit():
                    continue
                # Could be the signal
                sig = p.strip()
                sig_idx = j
                break
            if sig is None or sig == "":
                continue
            # The three vertices are the next 3 fields after the signal
            # that contain commas
            verts = []
            for p in parts[sig_idx + 1:]:
                if "," in p:
                    xy = p.split(",")
                    if len(xy) == 2:
                        try:
                            verts.append((float(xy[0]), float(xy[1])))
                        except ValueError:
                            pass
                if len(verts) == 3:
                    break
            if len(verts) != 3:
                continue
            triangle_vec = np.array([c for xy in verts for c in xy], dtype=float)
            rows.append((sig, triangle_vec))
    return rows

def load_experiment(exp_num):
    """
    Returns dict: chain -> list over generations 0..10 of list of (signal, triangle).
    """
    base = os.path.join(REPO, "data", f"experiment_{exp_num}")
    data = {}
    for chain in CHAINS_BY_EXP[exp_num]:
        chain_dir = os.path.join(base, chain)
        if not os.path.isdir(chain_dir):
            continue
        gens = []
        for g in range(N_GEN + 1):
            path = os.path.join(chain_dir, f"{g}s")
            if not os.path.exists(path):
                gens.append(None)
                continue
            rows = parse_static_file(path)
            gens.append(rows)
        data[chain] = gens
    return data

# ------------------------------------------------------------
# Alignment by triangle coordinates
# Since the static set's triangles are identical across generations for
# a given chain, we use the exact triangle vector as key.
# ------------------------------------------------------------

def triangle_key(t):
    # Quantize to integer to avoid float equality headaches (coords are ints anyway)
    return tuple(int(round(c)) for c in t)

def align_trajectories(chain_data):
    """
    chain_data: list over generations of list of (sig, triangle_vec)
    Returns: dict triangle_key -> list over generations of signal (or None).
    """
    trajectories = {}
    for g, rows in enumerate(chain_data):
        if rows is None:
            continue
        for sig, tri in rows:
            k = triangle_key(tri)
            if k not in trajectories:
                trajectories[k] = [None] * (N_GEN + 1)
            trajectories[k][g] = sig
    # Only keep triangles that have a signal in ALL 11 generations
    complete = {k: traj for k, traj in trajectories.items()
                if all(s is not None for s in traj)}
    return complete

# ------------------------------------------------------------
# Levenshtein-distance embedding
# ------------------------------------------------------------

def levenshtein(a, b):
    m, n = len(a), len(b)
    if m == 0:
        return n
    if n == 0:
        return m
    dp = np.zeros((m + 1, n + 1), dtype=np.int32)
    dp[:, 0] = np.arange(m + 1)
    dp[0, :] = np.arange(n + 1)
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if a[i-1] == b[j-1] else 1
            dp[i, j] = min(
                dp[i-1, j] + 1,
                dp[i, j-1] + 1,
                dp[i-1, j-1] + cost,
            )
    return int(dp[m, n])

def build_embedding(all_signals, n_anchors=40, dim=5, seed=0):
    """
    Take all signals in the experiment, sample n_anchors, compute signal ->
    dist vector to anchors, reduce to `dim` via SVD of the centered dist matrix.
    Returns a function signal -> R^d vector.
    """
    rng = np.random.default_rng(seed)
    unique_signals = sorted(set(all_signals))
    if len(unique_signals) <= n_anchors:
        anchors = unique_signals
    else:
        idx = rng.choice(len(unique_signals), size=n_anchors, replace=False)
        anchors = [unique_signals[i] for i in idx]
    # Precompute full distance matrix
    D = np.zeros((len(unique_signals), len(anchors)), dtype=float)
    for i, s in enumerate(unique_signals):
        for j, a in enumerate(anchors):
            D[i, j] = levenshtein(s, a)
    mean_col = D.mean(axis=0, keepdims=True)
    D_centered = D - mean_col
    U, S, Vt = np.linalg.svd(D_centered, full_matrices=False)
    # Build signal -> vector map in R^dim
    X = U[:, :dim] * S[:dim]
    sig_to_vec = dict(zip(unique_signals, X))
    anchors_info = {
        "n_anchors": len(anchors),
        "anchors": anchors,
        "mean_col": mean_col.flatten(),
        "singular_values": S.tolist(),
    }
    return sig_to_vec, anchors_info

# ------------------------------------------------------------
# Estimation
# ------------------------------------------------------------

def estimate(pairs, d):
    X = np.stack([p[0] for p in pairs])
    Y = np.stack([p[1] for p in pairs])
    mu_x = X.mean(axis=0)
    mu_y = Y.mean(axis=0)
    Xc = X - mu_x
    Yc = Y - mu_y
    A_hat = np.linalg.lstsq(Xc, Yc, rcond=None)[0].T
    R = Yc - Xc @ A_hat.T
    sigma2 = np.mean(np.sum(R ** 2, axis=1))
    lam2_eff = np.trace(A_hat @ A_hat.T) / d
    return A_hat, sigma2, lam2_eff, mu_y

def run_experiment(exp_num, dim=5, burn_in=3):
    print("=" * 70)
    print(f"Experiment {exp_num}: Carr, Smith, Cornish & Kirby (2017)")
    print("=" * 70)
    data = load_experiment(exp_num)
    print(f"Chains loaded: {list(data.keys())}")

    # Collect all signals across all chains/generations
    all_signals = []
    for chain, gens in data.items():
        for rows in gens:
            if rows is None:
                continue
            for sig, _ in rows:
                all_signals.append(sig)
    print(f"Total signal tokens: {len(all_signals)}, unique: {len(set(all_signals))}")

    # Build embedding once for this experiment
    sig_to_vec, info = build_embedding(all_signals, n_anchors=40, dim=dim, seed=0)
    print(f"Embedding: {dim}-dim via {info['n_anchors']} anchors; "
          f"top-5 singular values: {[round(s, 2) for s in info['singular_values'][:5]]}")

    # Build trajectories and pairs
    pairs = []
    all_vectors_by_gen = [[] for _ in range(N_GEN + 1)]
    n_complete_trajectories = 0
    for chain, gens in data.items():
        trajectories = align_trajectories(gens)
        n_complete_trajectories += len(trajectories)
        for k, traj in trajectories.items():
            vecs = [sig_to_vec[s] for s in traj]
            for g, v in enumerate(vecs):
                all_vectors_by_gen[g].append(v)
            for n in range(burn_in, N_GEN):
                pairs.append((vecs[n], vecs[n + 1]))
    print(f"Complete trajectories (triangles appearing in all {N_GEN + 1} gens): "
          f"{n_complete_trajectories}")
    print(f"Transmission pairs (burn_in={burn_in}): {len(pairs)}")

    # Estimate
    A_hat, sigma2, lam2_eff, mu_y = estimate(pairs, dim)
    V_pred = sigma2 / (1 - lam2_eff) if lam2_eff < 1 else float("inf")

    # Empirical V* from last 3 generations
    tail = []
    for g in range(N_GEN - 2, N_GEN + 1):  # gens 8, 9, 10
        vs = np.array(all_vectors_by_gen[g])
        tail.extend(list(vs - mu_y))
    tail = np.array(tail)
    V_emp = np.mean(np.sum(tail ** 2, axis=1))

    # Per-generation variance trajectory
    gen_V = []
    for g in range(N_GEN + 1):
        vs = np.array(all_vectors_by_gen[g])
        gen_V.append(float(np.mean(np.sum((vs - mu_y) ** 2, axis=1))))

    rel_err = abs(V_pred - V_emp) / max(V_emp, 1e-9)
    print()
    print(f"Estimated lambda_bar^2 = tr(A A^T)/d : {lam2_eff:.4f}")
    print(f"Estimated lambda_bar                : {np.sqrt(lam2_eff):.4f}")
    print(f"Estimated sigma^2                   : {sigma2:.4f}")
    print(f"Predicted V*  = sigma^2/(1-lam^2)   : {V_pred:.4f}")
    print(f"Empirical V*  (last 3 generations)  : {V_emp:.4f}")
    print(f"Relative error                      : {rel_err*100:.2f}%")
    print()
    print("Per-generation V_n:")
    for g, v in enumerate(gen_V):
        print(f"  gen {g:2d}: V_n = {v:.4f}")
    return {
        "exp_num": exp_num,
        "dim": dim,
        "burn_in": burn_in,
        "n_signal_tokens": len(all_signals),
        "n_unique_signals": len(set(all_signals)),
        "n_trajectories": n_complete_trajectories,
        "n_pairs": len(pairs),
        "lambda_bar2": float(lam2_eff),
        "lambda_bar": float(np.sqrt(lam2_eff)),
        "sigma2": float(sigma2),
        "V_predicted": float(V_pred),
        "V_empirical": float(V_emp),
        "relative_error_pct": float(rel_err * 100),
        "gen_V": gen_V,
    }

# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

if __name__ == "__main__":
    results = {}
    for exp in [1, 2]:
        results[exp] = run_experiment(exp, dim=5, burn_in=3)
        print()

    # Multi-seed robustness: repeat with different anchor samples
    print("=" * 70)
    print("Robustness: 10 different anchor-set samples per experiment")
    print("=" * 70)

    def run_with_seed(exp_num, seed, dim=5, burn_in=3):
        data = load_experiment(exp_num)
        all_signals = []
        for chain, gens in data.items():
            for rows in gens:
                if rows is None:
                    continue
                for sig, _ in rows:
                    all_signals.append(sig)
        sig_to_vec, _ = build_embedding(all_signals, n_anchors=40, dim=dim, seed=seed)
        pairs = []
        all_vectors_by_gen = [[] for _ in range(N_GEN + 1)]
        for chain, gens in data.items():
            trajectories = align_trajectories(gens)
            for k, traj in trajectories.items():
                vecs = [sig_to_vec[s] for s in traj]
                for g, v in enumerate(vecs):
                    all_vectors_by_gen[g].append(v)
                for n in range(burn_in, N_GEN):
                    pairs.append((vecs[n], vecs[n + 1]))
        A_hat, sigma2, lam2_eff, mu_y = estimate(pairs, dim)
        V_pred = sigma2 / (1 - lam2_eff) if lam2_eff < 1 else float("inf")
        tail = []
        for g in range(N_GEN - 2, N_GEN + 1):
            vs = np.array(all_vectors_by_gen[g])
            tail.extend(list(vs - mu_y))
        tail = np.array(tail)
        V_emp = np.mean(np.sum(tail ** 2, axis=1))
        return lam2_eff, sigma2, V_pred, V_emp

    robust = {}
    for exp in [1, 2]:
        preds, emps, lams, sigs = [], [], [], []
        for seed in range(10):
            lam, sig, p, e = run_with_seed(exp, seed)
            preds.append(p); emps.append(e); lams.append(lam); sigs.append(sig)
            print(f"  exp {exp} seed {seed:2d}: lam^2={lam:.3f} sigma^2={sig:.3f} "
                  f"V*_pred={p:.3f} V*_emp={e:.3f}")
        preds = np.array(preds); emps = np.array(emps)
        lams = np.array(lams); sigs = np.array(sigs)
        rel = np.abs(preds - emps) / emps
        robust[exp] = {
            "mean_lambda_bar2": float(lams.mean()),
            "sd_lambda_bar2": float(lams.std()),
            "mean_sigma2": float(sigs.mean()),
            "sd_sigma2": float(sigs.std()),
            "mean_V_predicted": float(preds.mean()),
            "sd_V_predicted": float(preds.std()),
            "mean_V_empirical": float(emps.mean()),
            "sd_V_empirical": float(emps.std()),
            "mean_rel_err_pct": float(rel.mean() * 100),
            "max_rel_err_pct": float(rel.max() * 100),
        }
        print()
        print(f"  Experiment {exp} across 10 anchor seeds:")
        print(f"    lambda_bar^2 = {lams.mean():.3f} ± {lams.std():.3f}")
        print(f"    sigma^2      = {sigs.mean():.3f} ± {sigs.std():.3f}")
        print(f"    V*_pred      = {preds.mean():.3f} ± {preds.std():.3f}")
        print(f"    V*_emp       = {emps.mean():.3f} ± {emps.std():.3f}")
        print(f"    rel err      = {rel.mean()*100:.2f}% (max {rel.max()*100:.2f}%)")
        print()

    # Save results
    with open(os.path.join(OUT, "real_data_results.json"), "w") as f:
        json.dump({"single_run": results, "multi_seed": robust}, f, indent=2)
    print("Saved real_data_results.json")

    # Plot V_n trajectories for both experiments
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    for ax, exp in zip(axes, [1, 2]):
        r = results[exp]
        ax.plot(range(N_GEN + 1), r["gen_V"], "bo-",
                label=r"$V_n$ (empirical)", markersize=7)
        ax.axhline(y=r["V_predicted"], color="r", linestyle="--",
                   label=fr"$V^*$ predicted = {r['V_predicted']:.2f}")
        ax.axhline(y=r["V_empirical"], color="g", linestyle=":",
                   label=fr"$V^*$ empirical (tail mean) = {r['V_empirical']:.2f}")
        ax.set_xlabel("Generation $n$", fontsize=12)
        ax.set_ylabel(r"$V_n$", fontsize=12)
        ax.set_title(f"Experiment {exp}  (Carr et al. 2017)\n"
                     fr"$\hat{{\bar\lambda}}^2 = {r['lambda_bar2']:.3f}$, "
                     fr"$\hat\sigma^2 = {r['sigma2']:.2f}$, "
                     fr"rel.err. {r['relative_error_pct']:.1f}%", fontsize=11)
        ax.legend(fontsize=9)
        ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT, "real_data_trajectories.png"), dpi=300)
    print("Saved real_data_trajectories.png")

    # Prediction vs empirical scatter over seeds, both experiments
    fig2, ax2 = plt.subplots(figsize=(6.5, 6))
    colors = {1: "tab:blue", 2: "tab:orange"}
    all_v = []
    for exp in [1, 2]:
        preds_list = []
        emps_list = []
        for seed in range(10):
            _, _, p, e = run_with_seed(exp, seed)
            preds_list.append(p); emps_list.append(e)
        ax2.scatter(emps_list, preds_list, s=100, c=colors[exp],
                    edgecolor="k", label=f"Experiment {exp}", zorder=3)
        all_v.extend(preds_list + emps_list)
    lo = min(all_v) * 0.9
    hi = max(all_v) * 1.1
    ax2.plot([lo, hi], [lo, hi], "k--", alpha=0.6, label="y = x")
    ax2.set_xlabel(r"Empirical $V^*$ (mean $\|s-\mu\|^2$, gens 8–10)", fontsize=11)
    ax2.set_ylabel(r"Predicted $V^* = \hat\sigma^2/(1-\hat{\bar\lambda}^2)$", fontsize=11)
    ax2.set_title("Real-data validation of Theorem 3.1\n"
                  "Carr, Smith, Cornish, Kirby (2017) — 10 anchor seeds", fontsize=11)
    ax2.legend(fontsize=10)
    ax2.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT, "real_data_pred_vs_emp.png"), dpi=300)
    print("Saved real_data_pred_vs_emp.png")

    print()
    print("DONE.")
