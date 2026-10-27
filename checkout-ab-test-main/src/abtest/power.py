"""Power analysis and sample-size planning for conversion-rate experiments."""
from __future__ import annotations

import numpy as np
from scipy import stats


def sample_size_per_arm(
    baseline: float, rel_mde: float, alpha: float = 0.05, power: float = 0.8
) -> int:
    """Users per arm to detect a relative lift ``rel_mde`` on a rate ``baseline``.

    Two-sided test of two proportions, with the variance evaluated under the
    alternative (unpooled), the standard normal-approximation formula:
        n = (z_{1-a/2} + z_{power})^2 * (p1(1-p1) + p2(1-p2)) / (p2 - p1)^2
    """
    p1 = baseline
    p2 = baseline * (1 + rel_mde)
    z_a = stats.norm.ppf(1 - alpha / 2)
    z_b = stats.norm.ppf(power)
    n = (z_a + z_b) ** 2 * (p1 * (1 - p1) + p2 * (1 - p2)) / (p2 - p1) ** 2
    return int(np.ceil(n))


def mde_for_sample(
    baseline: float, n_per_arm: int, alpha: float = 0.05, power: float = 0.8,
    variance_reduction: float = 0.0,
) -> float:
    """Smallest relative lift detectable with ``n_per_arm`` users per arm.

    ``variance_reduction`` (e.g. from CUPED) shrinks the variance by that
    fraction, which is equivalent to multiplying the sample by 1/(1-VR).
    """
    z = stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)
    var = 2 * baseline * (1 - baseline) * (1 - variance_reduction)
    return float(z * np.sqrt(var / n_per_arm) / baseline)


def power_for_effect(
    baseline: float, rel_lift: float, n_per_arm: int, alpha: float = 0.05
) -> float:
    """Probability a two-sided z-test detects a true relative lift."""
    p1, p2 = baseline, baseline * (1 + rel_lift)
    se = np.sqrt((p1 * (1 - p1) + p2 * (1 - p2)) / n_per_arm)
    z_a = stats.norm.ppf(1 - alpha / 2)
    shift = abs(p2 - p1) / se
    return float(stats.norm.sf(z_a - shift) + stats.norm.cdf(-z_a - shift))
