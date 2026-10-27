"""Frequentist tools for A/B tests, written from first principles on NumPy/SciPy.

Every function returns plain dicts so results serialize straight to JSON.
"""
from __future__ import annotations

import numpy as np
from scipy import stats

Z_975 = stats.norm.ppf(0.975)


# --------------------------------------------------------------------------- #
# Sample ratio mismatch
# --------------------------------------------------------------------------- #
def srm_test(n_control: int, n_treatment: int, expected_share: float = 0.5) -> dict:
    """Chi-square goodness-of-fit test that the split matches the design.

    A tiny p-value means the randomization or logging is broken and the
    experiment's results shouldn't be trusted until the cause is found.
    Industry practice is to alarm at p < 0.001.
    """
    observed = np.array([n_control, n_treatment], dtype=float)
    expected = observed.sum() * np.array([1 - expected_share, expected_share])
    chi2 = float(((observed - expected) ** 2 / expected).sum())
    p = float(stats.chi2.sf(chi2, df=1))
    return {
        "n_control": int(n_control),
        "n_treatment": int(n_treatment),
        "treatment_share": n_treatment / observed.sum(),
        "chi2": chi2,
        "p_value": p,
        "srm_detected": p < 0.001,
    }


# --------------------------------------------------------------------------- #
# Difference in means (works for binary and continuous metrics)
# --------------------------------------------------------------------------- #
def diff_in_means(y_control: np.ndarray, y_treatment: np.ndarray, alpha: float = 0.05) -> dict:
    """Welch z-test for a difference in means, with absolute and relative CIs.

    For a 0/1 metric this is the unpooled two-proportion z-test. With tens of
    thousands of users per arm, the normal approximation is excellent (CLT).

    The relative-lift CI uses the delta method on the ratio of means:
        Var(mT/mC) ~= Var(mT)/mC^2 + mT^2 Var(mC)/mC^4
    """
    yc = np.asarray(y_control, dtype=float)
    yt = np.asarray(y_treatment, dtype=float)
    mc, mt = yc.mean(), yt.mean()
    vc, vt = yc.var(ddof=1) / yc.size, yt.var(ddof=1) / yt.size
    diff = mt - mc
    se = np.sqrt(vc + vt)
    z = diff / se
    p = 2 * stats.norm.sf(abs(z))
    zc = stats.norm.ppf(1 - alpha / 2)

    rel = mt / mc - 1
    se_rel = np.sqrt(vt / mc**2 + mt**2 * vc / mc**4)
    return {
        "control_mean": mc,
        "treatment_mean": mt,
        "abs_diff": diff,
        "abs_ci": [diff - zc * se, diff + zc * se],
        "rel_lift": rel,
        "rel_ci": [rel - zc * se_rel, rel + zc * se_rel],
        "se": se,
        "z": z,
        "p_value": p,
        "n_control": int(yc.size),
        "n_treatment": int(yt.size),
    }


# --------------------------------------------------------------------------- #
# CUPED (Deng, Xu, Kohavi & Walker, 2013)
# --------------------------------------------------------------------------- #
def cuped_adjust(y: np.ndarray, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return the CUPED-adjusted outcome  y - (X - mean(X)) @ theta.

    theta is the OLS slope of y on pre-period covariates X, pooled over both
    arms. Because X is measured *before* assignment, it's independent of
    treatment, so the adjustment leaves the expected difference unchanged
    and removes the variance in y that X explains.
    """
    y = np.asarray(y, dtype=float)
    X = np.asarray(X, dtype=float)
    if X.ndim == 1:
        X = X[:, None]
    Xc = X - X.mean(axis=0)
    theta, *_ = np.linalg.lstsq(Xc, y - y.mean(), rcond=None)
    return y - Xc @ theta, theta


def cuped_test(
    y: np.ndarray, X: np.ndarray, is_treatment: np.ndarray, alpha: float = 0.05
) -> dict:
    """Diff-in-means on the CUPED-adjusted metric, plus the variance reduction."""
    is_treatment = np.asarray(is_treatment, dtype=bool)
    y = np.asarray(y, dtype=float)
    y_adj, theta = cuped_adjust(y, X)
    res = diff_in_means(y_adj[~is_treatment], y_adj[is_treatment], alpha)
    raw = diff_in_means(y[~is_treatment], y[is_treatment], alpha)
    res["theta"] = np.atleast_1d(theta).tolist()
    res["variance_reduction"] = 1 - (res["se"] / raw["se"]) ** 2
    res["ci_width_reduction"] = 1 - res["se"] / raw["se"]
    # Express the adjusted effect relative to the unadjusted control mean, so
    # it's comparable with the raw result. (CUPED shifts each arm's mean by
    # (mean_X_arm - mean_X) @ theta, which is zero in expectation.)
    mc = y[~is_treatment].mean()
    res["control_mean"] = mc
    res["treatment_mean"] = mc + res["abs_diff"]
    res["rel_lift"] = res["abs_diff"] / mc
    res["rel_ci"] = [res["abs_ci"][0] / mc, res["abs_ci"][1] / mc]
    return res


# --------------------------------------------------------------------------- #
# Ratio metrics (per-order metrics where the unit of randomization is the user)
# --------------------------------------------------------------------------- #
def ratio_metric_test(
    num_c: np.ndarray, den_c: np.ndarray, num_t: np.ndarray, den_t: np.ndarray, alpha: float = 0.05
) -> dict:
    """Compare sum(num)/sum(den) between arms, clustering by user.

    Orders from the same user aren't independent, so treating orders as
    i.i.d. understates the standard error. The delta method on per-user
    sums gives the correct variance:
        Var(N/D) ~= (1/n) * (s_N^2 - 2 R s_ND + R^2 s_D^2) / mean(D)^2
    """

    def ratio_and_var(num, den):
        num, den = np.asarray(num, float), np.asarray(den, float)
        n = num.size
        mn, md = num.mean(), den.mean()
        r = mn / md
        cov = np.cov(num, den, ddof=1)
        var = (cov[0, 0] - 2 * r * cov[0, 1] + r**2 * cov[1, 1]) / (md**2 * n)
        return r, var

    rc, vc = ratio_and_var(num_c, den_c)
    rt, vt = ratio_and_var(num_t, den_t)
    diff, se = rt - rc, np.sqrt(vc + vt)
    zc = stats.norm.ppf(1 - alpha / 2)
    rel = rt / rc - 1
    se_rel = np.sqrt(vt / rc**2 + rt**2 * vc / rc**4)
    return {
        "control": rc,
        "treatment": rt,
        "abs_diff": diff,
        "abs_ci": [diff - zc * se, diff + zc * se],
        "rel_lift": rel,
        "rel_ci": [rel - zc * se_rel, rel + zc * se_rel],
        "p_value": 2 * stats.norm.sf(abs(diff / se)),
    }


# --------------------------------------------------------------------------- #
# Bootstrap (for heavy-tailed metrics like revenue per user)
# --------------------------------------------------------------------------- #
def bootstrap_rel_lift(
    y_control: np.ndarray,
    y_treatment: np.ndarray,
    n_boot: int = 5_000,
    seed: int = 0,
    alpha: float = 0.05,
) -> dict:
    """Percentile bootstrap CI for the relative lift in means.

    Resamples users within each arm (the unit of randomization). Uses
    multinomial counts instead of index arrays, which is ~10x faster and
    mathematically identical.
    """
    rng = np.random.default_rng(seed)
    yc, yt = np.asarray(y_control, float), np.asarray(y_treatment, float)
    wc = rng.multinomial(yc.size, np.full(yc.size, 1 / yc.size), size=n_boot)
    wt = rng.multinomial(yt.size, np.full(yt.size, 1 / yt.size), size=n_boot)
    mc = wc @ yc / yc.size
    mt = wt @ yt / yt.size
    lifts = mt / mc - 1
    lo, hi = np.quantile(lifts, [alpha / 2, 1 - alpha / 2])
    return {
        "rel_lift": yt.mean() / yc.mean() - 1,
        "rel_ci": [float(lo), float(hi)],
        "p_two_sided_approx": float(2 * min((lifts <= 0).mean(), (lifts >= 0).mean())),
        "n_boot": n_boot,
    }


# --------------------------------------------------------------------------- #
# Multiple comparisons
# --------------------------------------------------------------------------- #
def holm_adjust(p_values: list[float]) -> list[float]:
    """Holm-Bonferroni step-down adjusted p-values (controls FWER)."""
    p = np.asarray(p_values, dtype=float)
    m = p.size
    order = np.argsort(p)
    adjusted = np.empty(m)
    running_max = 0.0
    for rank, idx in enumerate(order):
        running_max = max(running_max, (m - rank) * p[idx])
        adjusted[idx] = min(1.0, running_max)
    return adjusted.tolist()


def interaction_test(seg_a: dict, seg_b: dict) -> dict:
    """z-test that two independent segments have different absolute effects."""
    d = seg_a["abs_diff"] - seg_b["abs_diff"]
    se = np.sqrt(seg_a["se"] ** 2 + seg_b["se"] ** 2)
    return {"diff_of_effects": d, "z": d / se, "p_value": 2 * stats.norm.sf(abs(d / se))}
