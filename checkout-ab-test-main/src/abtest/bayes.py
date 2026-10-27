"""Bayesian read-out of a conversion experiment (Beta-Binomial model).

The frequentist p-value answers "how surprising is this data if there's no
effect?". Stakeholders usually want something else: "how likely is it that
B is better, and what do we lose if we ship it and it isn't?" The posterior
answers both directly.
"""
from __future__ import annotations

import numpy as np


def beta_binomial_readout(
    conv_c: int, n_c: int, conv_t: int, n_t: int,
    prior_a: float = 1.0, prior_b: float = 1.0,
    draws: int = 400_000, seed: int = 0,
) -> dict:
    """Monte Carlo summary of the posterior for the treatment effect.

    With a Beta(a, b) prior and binomial data, each arm's posterior is
    Beta(a + conversions, b + non-conversions): conjugacy, no MCMC needed.

    expected_loss_* is E[max(other - this, 0)]: the conversion rate you
    expect to give up by shipping that arm. A common decision rule is to ship
    when the expected loss is below a "threshold of caring".
    """
    rng = np.random.default_rng(seed)
    pc = rng.beta(prior_a + conv_c, prior_b + n_c - conv_c, draws)
    pt = rng.beta(prior_a + conv_t, prior_b + n_t - conv_t, draws)
    lift = pt / pc - 1
    return {
        "prob_treatment_better": float((pt > pc).mean()),
        "prob_lift_above_2pct": float((lift > 0.02).mean()),
        "expected_loss_ship_treatment": float(np.maximum(pc - pt, 0).mean()),
        "expected_loss_keep_control": float(np.maximum(pt - pc, 0).mean()),
        "rel_lift_mean": float(lift.mean()),
        "rel_lift_ci95": np.quantile(lift, [0.025, 0.975]).tolist(),
        "lift_draws": lift,  # removed before JSON export
    }
