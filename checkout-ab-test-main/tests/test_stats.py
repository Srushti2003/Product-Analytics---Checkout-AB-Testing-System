"""Unit tests for the statistics module.  Run:  python -m unittest discover tests"""
import sys
import unittest
from pathlib import Path

import numpy as np
from scipy import stats as sps

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from abtest import bayes, power, stats  # noqa: E402


class TestSRM(unittest.TestCase):
    def test_balanced_split_passes(self):
        self.assertFalse(stats.srm_test(50_000, 50_100)["srm_detected"])

    def test_skewed_split_is_flagged(self):
        self.assertTrue(stats.srm_test(50_000, 51_500)["srm_detected"])

    def test_matches_scipy_chisquare(self):
        ours = stats.srm_test(30_358, 31_202)["p_value"]
        ref = sps.chisquare([30_358, 31_202]).pvalue
        self.assertAlmostEqual(ours, ref, places=10)


class TestDiffInMeans(unittest.TestCase):
    def test_matches_welch_ttest_at_large_n(self):
        rng = np.random.default_rng(0)
        a, b = rng.normal(0, 1, 20_000), rng.normal(0.03, 1.3, 20_000)
        ours = stats.diff_in_means(a, b)["p_value"]
        ref = sps.ttest_ind(b, a, equal_var=False).pvalue
        self.assertAlmostEqual(ours, ref, places=4)

    def test_ci_contains_estimate(self):
        rng = np.random.default_rng(1)
        r = stats.diff_in_means(rng.binomial(1, 0.1, 5_000), rng.binomial(1, 0.12, 5_000))
        self.assertLess(r["abs_ci"][0], r["abs_diff"])
        self.assertGreater(r["abs_ci"][1], r["abs_diff"])


class TestCUPED(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(2)
        n = 40_000
        self.x = rng.normal(size=n)
        self.t = rng.random(n) < 0.5
        self.y = 2 * self.x + rng.normal(size=n) + 0.05 * self.t  # true effect 0.05

    def test_reduces_variance_by_r_squared(self):
        r = stats.cuped_test(self.y, self.x, self.t)
        r2 = np.corrcoef(self.x, self.y)[0, 1] ** 2
        self.assertAlmostEqual(r["variance_reduction"], r2, delta=0.01)

    def test_estimate_is_unbiased_and_theta_correct(self):
        r = stats.cuped_test(self.y, self.x, self.t)
        self.assertAlmostEqual(r["theta"][0], 2.0, delta=0.02)
        self.assertLess(abs(r["abs_diff"] - 0.05), 3 * r["se"])


class TestRatioMetric(unittest.TestCase):
    def test_equals_iid_formula_when_one_order_per_user(self):
        rng = np.random.default_rng(3)
        num_c, num_t = rng.lognormal(4, 0.5, 3_000), rng.lognormal(4, 0.5, 3_000)
        ones = np.ones(3_000)
        r = stats.ratio_metric_test(num_c, ones, num_t, ones)
        d = stats.diff_in_means(num_c, num_t)
        self.assertAlmostEqual(r["abs_diff"], d["abs_diff"], places=8)
        self.assertAlmostEqual(r["p_value"], d["p_value"], places=6)


class TestHolm(unittest.TestCase):
    def test_known_values(self):
        adj = stats.holm_adjust([0.01, 0.04, 0.03, 0.005])
        np.testing.assert_allclose(adj, [0.03, 0.06, 0.06, 0.02])


class TestPower(unittest.TestCase):
    def test_sample_size_gives_target_power(self):
        n = power.sample_size_per_arm(0.11, 0.07)
        self.assertAlmostEqual(power.power_for_effect(0.11, 0.07, n), 0.80, delta=0.005)

    def test_mde_shrinks_with_variance_reduction(self):
        self.assertLess(
            power.mde_for_sample(0.11, 30_000, variance_reduction=0.2),
            power.mde_for_sample(0.11, 30_000),
        )


class TestBayes(unittest.TestCase):
    def test_identical_arms_give_coin_flip(self):
        r = bayes.beta_binomial_readout(1_000, 10_000, 1_000, 10_000, draws=200_000)
        self.assertAlmostEqual(r["prob_treatment_better"], 0.5, delta=0.01)

    def test_clear_winner(self):
        r = bayes.beta_binomial_readout(1_000, 10_000, 1_300, 10_000)
        self.assertGreater(r["prob_treatment_better"], 0.999)


class TestBootstrap(unittest.TestCase):
    def test_agrees_with_delta_method(self):
        rng = np.random.default_rng(4)
        a, b = rng.exponential(10, 20_000), rng.exponential(10.5, 20_000)
        boot = stats.bootstrap_rel_lift(a, b, n_boot=4_000, seed=0)["rel_ci"]
        delta = stats.diff_in_means(a, b)["rel_ci"]
        np.testing.assert_allclose(boot, delta, atol=0.004)


if __name__ == "__main__":
    unittest.main()
