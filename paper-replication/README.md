# Stationary Variance of Iterated Cultural Transmission — Replication Code

Replication code for the empirical verification (§4) of:

> Zhao, D. (2026). *The Stationary Distribution of Iterated Cultural Transmission: A Rate-Distortion Theorem and Its Empirical Verification.* Submitted to *Cognitive Science*.

The paper proves a stationary-variance theorem $V^* \le \sigma^2/(1-\lambda^2)$ for iterated cultural transmission modeled as a Markov kernel with $\lambda$-contractive systematic component, and verifies it on the publicly released iterated-learning data of Carr, Smith, Cornish & Kirby (2017, *Cognitive Science*).

This repository contains the analysis code, the pipeline configuration, and the pre-computed results used in the manuscript's §4.4.

## Repository contents

| File | Purpose |
|---|---|
| `real_data_analysis.py` | Main pipeline: load Carr 2017 data → Levenshtein embedding → OLS estimation of $\hat A, \hat\sigma^2, \hat{\bar\lambda}^2$ → headline $V^*_\text{pred}$ vs. $V^*_\text{emp}$ comparison for Experiments 1 and 2. Produces Table 4.4 and Figures `real_data_trajectories.png`, `real_data_pred_vs_emp.png`. |
| `real_data_robustness.py` | Three robustness analyses: (R1) 48-cell hyperparameter grid (`d` × `burn_in` × `n_anchors`); (R2) leave-one-chain-out cross-validation; (R3) per-generation convergence-rate fit. Produces Figures `real_data_convergence_exp1.png`, `real_data_convergence_exp2.png`. |
| `real_data_results.json` | Pre-computed Experiment 1 / Experiment 2 results (headline table). |
| `real_data_robustness.json` | Pre-computed hyperparameter-grid and LOCO results. |

## Data source

The raw iterated-learning data is **not** redistributed in this repository. Clone the original dataset (Carr et al. 2017) from:

```
git clone https://github.com/jwcarr/flatlanders.git
```

The pipeline expects the dataset path to be set via the `REPO` constant at the top of `real_data_analysis.py` (default: `./flatlanders_repo`). Edit this constant to point at your local clone before running.

## Requirements

- Python ≥ 3.9
- NumPy ≥ 1.22
- SciPy ≥ 1.8
- scikit-learn ≥ 1.0 (for OLS / SVD)
- Matplotlib ≥ 3.5 (figure generation only)
- python-Levenshtein ≥ 0.20 (string distance kernel)

Install dependencies:

```
pip install numpy scipy scikit-learn matplotlib python-Levenshtein
```

## Reproducing the headline results

The full pipeline (Experiment 1 + Experiment 2 + figures) runs in roughly 1–2 minutes on a 2024-class laptop:

```
python real_data_analysis.py
```

This regenerates `real_data_results.json` and the headline figures. Compare the output against the manuscript's Table 4.4 — relative errors should match within bootstrap noise (10 anchor seeds).

The full robustness grid (48 hyperparameter cells × 5 anchor seeds, ≈ 240 pipeline runs) takes 30–60 minutes:

```
python real_data_robustness.py
```

This regenerates `real_data_robustness.json` and the convergence-rate figures.

## Pipeline configuration

The headline run uses:

- `d = 5` (embedding dimension after SVD)
- `burn_in = 3` (discard first 3 generations before estimating $\hat A$)
- `n_anchors = 40` (Levenshtein-distance anchor strings)
- `n_bootstrap = 10` (anchor resampling)

All three knobs are explored in the robustness grid. The direction of the $V^*_\text{pred}/V^*_\text{emp}$ ratio (above 1 for Exp. 1, below 1 for Exp. 2) is preserved in 100% of the 48 cells; see manuscript §4.4 for the structural interpretation.

## Mapping the codebase to the manuscript

- **§4.2 Step 1 (Embedding)** → `real_data_analysis.build_embedding()`
- **§4.2 Steps 2–5 (Estimate $\hat T_C, \hat s^*, \hat\lambda, \hat\sigma^2$)** → `real_data_analysis.estimate()`
- **§4.3 Predictions and tests** → `real_data_analysis.predict_and_compare()`
- **§4.4 Table 4.4** → output of `real_data_analysis.py main()`
- **§4.4 Robustness (i) Hyperparameter grid** → `real_data_robustness.run_grid()`
- **§4.4 Robustness (ii) LOCO** → `real_data_robustness.run_loco()`
- **§4.4 Robustness (iii) Convergence rate** → `real_data_robustness.fit_convergence_rate()`

## Citation

If you use this code, please cite:

```
@article{zhao2026stationary,
  author  = {Zhao, Dengwu},
  title   = {The Stationary Distribution of Iterated Cultural Transmission:
             A Rate-Distortion Theorem and Its Empirical Verification},
  journal = {Cognitive Science},
  year    = {2026},
  note    = {Submitted}
}
```

And the underlying dataset:

```
@article{carr2017cultural,
  author  = {Carr, Jon W. and Smith, Kenny and Cornish, Hannah and Kirby, Simon},
  title   = {The cultural evolution of structured languages in an open-ended,
             continuous world},
  journal = {Cognitive Science},
  volume  = {41},
  number  = {4},
  pages   = {892--923},
  year    = {2017},
  doi     = {10.1111/cogs.12371}
}
```

## License

MIT License — see `LICENSE` for full text. The redistributed dataset (Carr et al. 2017) retains its original license terms; consult `jwcarr/flatlanders` directly.

## Contact

Dengwu Zhao — zdwsjtu@gmail.com — ORCID: [0009-0000-3139-8283](https://orcid.org/0009-0000-3139-8283)
