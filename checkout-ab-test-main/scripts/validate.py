"""Check that the analysis methods do what they claim.

1. Score: compare this experiment's estimates with the hidden ground truth.
2. A/A (permutation): shuffle the treatment labels on the real data 2,000
   times. A valid test should flag ~5% of shuffles at alpha = 0.05.
3. Coverage: simulate 300 fresh experiments from the same generator.
   95% CIs should contain the true effect ~95% of the time, and CUPED
   intervals should be narrower without losing coverage.
4. Peeking: simulate A/A tests read daily and stopped at the first
   p < 0.05, to show why the plan forbids it.

Usage:  python scripts/validate.py   (after build_db.py and run_analysis.py)
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from abtest import plots, stats  # noqa: E402
from abtest.plots import plt  # noqa: E402
from abtest.simulate import simulate_experiment  # noqa: E402

FIG = ROOT / "reports" / "figures"
COVARIATES = ["pre_orders", "pre_sessions"]


def z_pvalues(y: np.ndarray, T: np.ndarray) -> np.ndarray:
    """Vectorised Welch z-test p-values for many label vectors at once.

    y: (n,) outcome; T: (n_sims, n) boolean treatment labels.
    """
    nt = T.sum(axis=1)
    nc = T.shape[1] - nt
    st, st2 = T @ y, T @ (y**2)
    sc, sc2 = y.sum() - st, (y**2).sum() - st2
    mt, mc = st / nt, sc / nc
    vt = (st2 - nt * mt**2) / (nt - 1)
    vc = (sc2 - nc * mc**2) / (nc - 1)
    z = (mt - mc) / np.sqrt(vt / nt + vc / nc)
    return 2 * norm.sf(np.abs(z))


def aa_permutation(m: pd.DataFrame, n_sims: int = 2_000, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    y = m.converted.to_numpy(float)
    y_cuped, _ = stats.cuped_adjust(y, m[COVARIATES].to_numpy(float))
    n = y.size
    p_raw, p_cup = [], []
    for _ in range(n_sims // 200):  # batches keep memory small
        T = np.argsort(rng.random((200, n)), axis=1) < n // 2  # exact 50/50 shuffles
        T = T.astype(float)
        p_raw.append(z_pvalues(y, T))
        p_cup.append(z_pvalues(y_cuped, T))
    p_raw, p_cup = np.concatenate(p_raw), np.concatenate(p_cup)
    return {
        "n_sims": n_sims,
        "false_positive_rate_raw": float((p_raw < 0.05).mean()),
        "false_positive_rate_cuped": float((p_cup < 0.05).mean()),
        "p_raw": p_raw,
        "p_cuped": p_cup,
    }


def coverage_study(n_sims: int = 300) -> dict:
    rows = []
    for seed in range(1_000, 1_000 + n_sims):
        sim = simulate_experiment(n_users=60_000, seed=seed)
        u = sim["user_level"]
        truth = sim["truth"]["overall"]["abs_lift"]
        is_t = (u.variant == "treatment").to_numpy()
        y = u.converted.to_numpy(float)
        raw = stats.diff_in_means(y[~is_t], y[is_t])
        cup = stats.cuped_test(y, u[COVARIATES].to_numpy(float), is_t)
        rows.append(
            {
                "truth": truth,
                "raw_est": raw["abs_diff"],
                "cuped_est": cup["abs_diff"],
                "raw_covers": raw["abs_ci"][0] <= truth <= raw["abs_ci"][1],
                "cuped_covers": cup["abs_ci"][0] <= truth <= cup["abs_ci"][1],
                "raw_width": raw["abs_ci"][1] - raw["abs_ci"][0],
                "cuped_width": cup["abs_ci"][1] - cup["abs_ci"][0],
            }
        )
    df = pd.DataFrame(rows)
    return {
        "n_sims": n_sims,
        "coverage_raw": float(df.raw_covers.mean()),
        "coverage_cuped": float(df.cuped_covers.mean()),
        "bias_raw_pp": float((df.raw_est - df.truth).mean() * 100),
        "bias_cuped_pp": float((df.cuped_est - df.truth).mean() * 100),
        "rmse_raw_pp": float(np.sqrt(((df.raw_est - df.truth) ** 2).mean()) * 100),
        "rmse_cuped_pp": float(np.sqrt(((df.cuped_est - df.truth) ** 2).mean()) * 100),
        "mean_ci_width_raw_pp": float(df.raw_width.mean() * 100),
        "mean_ci_width_cuped_pp": float(df.cuped_width.mean() * 100),
    }


def peeking_study(n_sims: int = 20_000, days: int = 14, users_per_day_per_arm: int = 2_143,
                  p: float = 0.11, seed: int = 1) -> dict:
    """A/A tests analysed once per day; 'stop' at the first p < 0.05."""
    rng = np.random.default_rng(seed)
    conv_c = rng.binomial(users_per_day_per_arm, p, (n_sims, days)).cumsum(axis=1)
    conv_t = rng.binomial(users_per_day_per_arm, p, (n_sims, days)).cumsum(axis=1)
    n = users_per_day_per_arm * np.arange(1, days + 1)
    pc, pt = conv_c / n, conv_t / n
    se = np.sqrt(pc * (1 - pc) / n + pt * (1 - pt) / n)
    sig = 2 * norm.sf(np.abs((pt - pc) / se)) < 0.05
    ever = np.maximum.accumulate(sig, axis=1)
    return {
        "n_sims": n_sims,
        "fpr_fixed_horizon": float(sig[:, -1].mean()),
        "fpr_by_number_of_looks": ever.mean(axis=0).tolist(),
    }


def main() -> None:
    results = json.loads((ROOT / "reports" / "results.json").read_text())
    truth = json.loads((ROOT / "data" / "ground_truth.json").read_text())

    con = sqlite3.connect(ROOT / "data" / "experiment.db")
    con.executescript((ROOT / "sql" / "01_clean_assignments.sql").read_text())
    m = pd.read_sql((ROOT / "sql" / "04_user_metrics.sql").read_text(), con)

    # 1. Score against the answer key
    cup = results["primary"]["cuped"]
    late = results["late_cohorts"]
    score = {
        "true_rel_lift_during_test": truth["overall"]["rel_lift"],
        "estimated_rel_lift": cup["rel_lift"],
        "estimate_ci": cup["rel_ci"],
        "ci_contains_truth": cup["rel_ci"][0] <= truth["overall"]["rel_lift"] <= cup["rel_ci"][1],
        "true_steady_state_rel_lift": truth["overall_steady_state"]["rel_lift"],
        "late_cohort_estimate": late["rel_lift"],
        "late_cohort_ci": late["rel_ci"],
        "late_ci_contains_steady_state": late["rel_ci"][0] <= truth["overall_steady_state"]["rel_lift"] <= late["rel_ci"][1],
        # Platform only: the analysis defines "returning" from observed
        # pre-period sessions, which isn't identical to the simulator's flag.
        "segments": {
            k: {"true": truth[k.split("=")[1]]["rel_lift"], "estimate": v["rel_lift"], "ci": v["rel_ci"],
                "ci_contains_truth": v["rel_ci"][0] <= truth[k.split("=")[1]]["rel_lift"] <= v["rel_ci"][1]}
            for k, v in results["segments"].items() if k.startswith("platform")
        },
    }
    print("scored against ground truth")

    aa = aa_permutation(m)
    print(f"A/A: FPR raw {aa['false_positive_rate_raw']:.3f}, CUPED {aa['false_positive_rate_cuped']:.3f}")
    cov = coverage_study()
    print(f"coverage: raw {cov['coverage_raw']:.3f}, CUPED {cov['coverage_cuped']:.3f}")
    peek = peeking_study()
    print(f"peeking: fixed {peek['fpr_fixed_horizon']:.3f}, daily {peek['fpr_by_number_of_looks'][-1]:.3f}")

    # ---- figures -------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.2), sharey=True)
    for ax, key, color, label in [
        (axes[0], "p_raw", plots.NEUTRAL, "z-test"),
        (axes[1], "p_cuped", plots.BLUE, "CUPED z-test"),
    ]:
        ax.hist(aa[key], bins=20, range=(0, 1), color=color, edgecolor=plots.SURFACE, linewidth=2)
        ax.axhline(aa["n_sims"] / 20, color=plots.TEXT_2, lw=1, ls="--")
        fpr = aa["false_positive_rate_raw" if key == "p_raw" else "false_positive_rate_cuped"]
        ax.set_title(label, fontsize=11.5, pad=20)
        ax.text(0, 1.025, f"false-positive rate at α = 0.05: {fpr:.1%}", transform=ax.transAxes,
                fontsize=9, color=plots.TEXT_2, va="bottom")
        ax.set_xlabel("p-value")
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("A/A shuffles")
    fig.suptitle(f"{aa['n_sims']:,} A/A shuffles give flat p-values: the tests are calibrated",
                 x=0.01, ha="left", fontsize=13, fontweight="bold", color=plots.TEXT)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(FIG / "04_aa_test.png", bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 3.3))
    looks = np.arange(1, 15)
    fpr = np.array(peek["fpr_by_number_of_looks"]) * 100
    ax.plot(looks, fpr, color=plots.ORANGE, lw=2, marker="o", ms=6, mec=plots.SURFACE, mew=1.5)
    ax.axhline(5, color=plots.NEUTRAL, lw=1, ls="--")
    ax.text(1.3, 5.6, "nominal 5% (read once, at the end)", color=plots.TEXT_2, fontsize=9, va="bottom")
    ax.annotate(f"{fpr[-1]:.0f}%", (14, fpr[-1]), xytext=(8, 0), textcoords="offset points",
                va="center", fontsize=10, color=plots.TEXT, fontweight="bold")
    ax.set_xlim(0.5, 15.8)
    ax.set_ylim(0, max(fpr) * 1.2)
    ax.set_xticks([1, 4, 7, 10, 14])
    ax.set_xlabel("Days the dashboard was checked (stop at first p < 0.05)")
    ax.set_ylabel("False-positive rate (%)")
    ax.set_title(f"Stopping at the first daily win: {fpr[-1]:.0f}% false positives, not 5%")
    plots.subtitle(ax, f"{peek['n_sims']:,} simulated A/A tests with no true effect")
    plots.save(fig, FIG / "05_peeking.png")

    for k in ["p_raw", "p_cuped"]:
        aa.pop(k)
    out = {"score": score, "aa_permutation": aa, "coverage": cov, "peeking": peek}
    (ROOT / "reports" / "validation.json").write_text(json.dumps(out, indent=2, default=float))
    print(json.dumps({k: v for k, v in out.items() if k != "peeking"}, indent=2, default=float))


if __name__ == "__main__":
    main()
