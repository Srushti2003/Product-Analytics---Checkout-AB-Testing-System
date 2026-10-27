"""Generate a realistic checkout A/B experiment with a known ground truth.

Scenario
--------
An online retailer tests a new *one-page checkout* (treatment) against the
current three-step checkout (control). Users are randomized 50/50 on their
first visit during a 14-day enrollment window and followed for 7 days.

Why simulate?
-------------
Real experiment data never tells you the true effect, so you can't check
whether your analysis got the right answer. Here every user carries both
potential outcomes, which gives us an answer key (``ground_truth.json``) that
the analysis never reads. It is only used afterwards to score the estimate.

The data-generating process has the messy parts that real experiment data has:
  * user heterogeneity (a latent "engagement" trait drives both pre-period
    and in-experiment behaviour -> this is what CUPED exploits)
  * a heterogeneous effect (mobile users benefit more than desktop users)
  * a novelty effect for returning users that decays over time
  * bot traffic that disproportionately lands in treatment (-> SRM)
  * a logging bug that assigns a few users to both arms
  * duplicated assignment events
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

EXPERIMENT_START = pd.Timestamp("2026-03-02 00:00:00")
ENROLL_DAYS = 14
OUTCOME_DAYS = 7
PRE_DAYS = 28


@dataclass(frozen=True)
class Effects:
    """True treatment effects, on the per-session log-odds of purchasing."""

    mobile_logodds: float = 0.13
    desktop_logodds: float = 0.01
    novelty_logodds: float = 0.60       # extra lift for returning users at launch
    novelty_halflife_days: float = 3.0  # ...which halves every 3 days
    aov_multiplier: float = 0.99        # one-page checkout -> slightly smaller baskets
    refund_multiplier: float = 1.05     # guardrail: refunds up 5% (relative)


NO_EFFECT = Effects(0.0, 0.0, 0.0, 3.0, 1.0, 1.0)


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def _aggregate_prob_any(user_idx: np.ndarray, p: np.ndarray, n_users: int) -> np.ndarray:
    """P(at least one success) per user, given independent per-session probabilities."""
    log_none = np.bincount(user_idx, weights=np.log1p(-p), minlength=n_users)
    return 1.0 - np.exp(log_none)


def simulate_experiment(
    n_users: int = 60_000,
    seed: int = 2026,
    effects: Effects = Effects(),
    treat_share: float = 0.5,
) -> dict:
    """Simulate human users, their sessions and orders.

    Returns a dict with DataFrames ``users``, ``sessions``, ``orders`` (event
    level, times in days relative to EXPERIMENT_START), a user-level
    ``user_level`` frame, and ``truth`` (the sample average treatment effect).
    """
    rng = np.random.default_rng(seed)
    n = n_users
    uid = np.arange(n)

    mobile = rng.random(n) < 0.62
    country = rng.choice(["US", "CA", "UK", "DE"], size=n, p=[0.55, 0.15, 0.18, 0.12])
    returning = rng.random(n) < 0.55
    engagement = rng.normal(size=n)                       # latent, never observed
    treat = rng.random(n) < treat_share
    assign_day = rng.uniform(0, ENROLL_DAYS, n)

    base_logit = -3.25 + 0.75 * engagement - 0.35 * mobile + 0.35 * returning
    log_aov = 3.95 + 0.12 * engagement

    # ---- pre-period (28 days before assignment; only returning users) ------
    pre_k = np.where(returning, rng.poisson(np.exp(0.9 + 0.7 * engagement)), 0)
    pre_user = np.repeat(uid, pre_k)
    pre_day = assign_day[pre_user] - rng.uniform(0.01, PRE_DAYS, pre_user.size)
    pre_conv = rng.random(pre_user.size) < _sigmoid(base_logit[pre_user])

    # ---- experiment period (7 days after assignment) -----------------------
    k = 1 + rng.poisson(np.exp(0.15 + 0.45 * engagement))  # >=1: assignment visit
    s_user = np.repeat(uid, k)
    first = np.r_[True, s_user[1:] != s_user[:-1]]
    offset = np.where(first, 0.0, rng.uniform(0, OUTCOME_DAYS, s_user.size))
    s_day = assign_day[s_user] + offset

    tau = np.where(mobile, effects.mobile_logodds, effects.desktop_logodds)[s_user]
    novelty = (
        effects.novelty_logodds
        * returning[s_user]
        * 0.5 ** (s_day / effects.novelty_halflife_days)
    )
    p0 = _sigmoid(base_logit[s_user])
    p1 = _sigmoid(base_logit[s_user] + tau + novelty)
    p = np.where(treat[s_user], p1, p0)
    s_conv = rng.random(s_user.size) < p

    # ---- orders ------------------------------------------------------------
    def make_orders(users, days, period):
        m = users.size
        t = treat[users] & (period == "experiment")
        revenue = np.exp(log_aov[users] + rng.normal(0, 0.55, m))
        revenue = np.where(t, revenue * effects.aov_multiplier, revenue)
        refund_p = np.where(t, 0.06 * effects.refund_multiplier, 0.06)
        return pd.DataFrame(
            {
                "user_id": users,
                "day": days + 5 / 1440,  # order placed ~5 minutes into the session
                "revenue": np.round(revenue, 2),
                "refunded": (rng.random(m) < refund_p).astype(int),
                "period": period,
            }
        )

    orders = pd.concat(
        [
            make_orders(pre_user[pre_conv], pre_day[pre_conv], "pre"),
            make_orders(s_user[s_conv], s_day[s_conv], "experiment"),
        ],
        ignore_index=True,
    )

    sessions = pd.concat(
        [
            pd.DataFrame({"user_id": pre_user, "day": pre_day}),
            pd.DataFrame({"user_id": s_user, "day": s_day}),
        ],
        ignore_index=True,
    )

    users = pd.DataFrame(
        {
            "user_id": uid,
            "platform": np.where(mobile, "mobile", "desktop"),
            "country": country,
            "variant": np.where(treat, "treatment", "control"),
            "assign_day": assign_day,
        }
    )

    # ---- ground truth: sample average treatment effect on conversion -------
    pc0 = _aggregate_prob_any(s_user, p0, n)
    pc1 = _aggregate_prob_any(s_user, p1, n)

    def sate(mask):
        c, t = pc0[mask].mean(), pc1[mask].mean()
        return {"control_rate": c, "treatment_rate": t, "abs_lift": t - c, "rel_lift": t / c - 1}

    # Long-run effect: what the lift would be once novelty has fully worn off
    pc1_steady = _aggregate_prob_any(s_user, _sigmoid(base_logit[s_user] + tau), n)
    steady = {
        "treatment_rate": pc1_steady.mean(),
        "rel_lift": pc1_steady.mean() / pc0.mean() - 1,
        "abs_lift": pc1_steady.mean() - pc0.mean(),
    }

    truth = {
        "overall": sate(np.ones(n, bool)),
        "overall_steady_state": steady,
        "mobile": sate(mobile),
        "desktop": sate(~mobile),
        "new": sate(~returning),
        "returning": sate(returning),
        "effects": asdict(effects),
    }

    # ---- user-level table (used by fast validation simulations) -------------
    exp_orders = np.bincount(s_user, weights=s_conv, minlength=n)
    pre_orders = np.bincount(pre_user, weights=pre_conv, minlength=n)
    user_level = pd.DataFrame(
        {
            "variant": users["variant"],
            "platform": users["platform"],
            "is_new": (~returning).astype(int),
            "pre_sessions": pre_k,
            "pre_orders": pre_orders,
            "converted": (exp_orders > 0).astype(int),
            "orders": exp_orders,
        }
    )

    return {
        "users": users,
        "sessions": sessions,
        "orders": orders,
        "user_level": user_level,
        "truth": truth,
    }
