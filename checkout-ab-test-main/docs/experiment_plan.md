# Experiment plan: one-page checkout (`checkout_one_page_v1`)

*Written before launch. The analysis follows this plan; anything not listed here is labelled exploratory.*

## Hypothesis

Collapsing the three-step checkout into a single page removes friction, so
more visitors complete a purchase. We expect the biggest gain on **mobile**,
where each extra step means another page load on a small screen.

## Design

| | |
|---|---|
| Unit of randomization | user (sticky, assigned on first visit during enrollment) |
| Split | 50 / 50 |
| Enrollment window | 14 days (2026-03-02 → 2026-03-15), two full weekly cycles |
| Outcome window | 7 days after each user's assignment |
| Eligible population | all visitors, excluding bot-flagged users and users with conflicting assignments |

## Metrics

| Role | Metric | Definition |
|---|---|---|
| **Primary** | Conversion | share of users with ≥1 order in their 7-day window |
| Secondary | Revenue per user | gross order revenue per user in the window (zeros included) |
| Guardrail | Refund rate | refunded orders / orders (must not rise significantly) |
| Guardrail | Average order value | revenue / orders (must not fall significantly: 95% CI entirely below 0 = fail) |
| Health check | Sample ratio | chi-square vs. 50/50; alarm at p < 0.001 |

## Power

* Baseline 7-day conversion from last month's dashboards: **≈ 11%**
* Minimum detectable effect we care about: **+7% relative** (11.0% → 11.8%).
  Below that, the engineering cost of maintaining two checkouts isn't worth it.
* α = 0.05 two-sided, power = 80% → **26,708 users per arm** (`abtest.power.sample_size_per_arm`)
* Expected traffic ≈ 4,300 eligible users/day across both arms → 14 days gives ≈ 30,000 per arm,
  a ~12% buffer for exclusions.
* **No peeking.** Results are read once, after the last cohort's outcome
  window closes (2026-03-22). See `reports/figures/06_peeking.png` for why.

## Analysis

1. Data-quality funnel and SRM check. **Stop if SRM persists after cleaning.**
2. Primary metric: unpooled two-proportion z-test, with the 95% CI on the
   relative lift (delta method).
3. Variance reduction: CUPED using pre-period (28-day) orders and sessions.
   CUPED is the headline estimate if it gives a narrower interval; the raw
   estimate is also reported.
4. Bayesian read-out (Beta(1,1) prior): P(treatment better), expected loss.
5. Revenue per user: difference in means with a bootstrap CI (revenue is heavy-tailed).
6. Pre-registered segments: **platform** (mobile / desktop) and **user type**
   (new / returning), Holm-corrected. Any other cut is exploratory.
7. Novelty check: lift by enrollment-day cohort, returning vs. new users.
   If the lift trends down, report the lift among cohorts enrolled in week 2
   as a long-run proxy alongside the headline number.

## Decision rule

* **Ship** if the primary metric is significant (p < 0.05) and positive, and no guardrail fails.
* **Ship to a segment only** if the overall effect isn't significant but a
  pre-registered segment is, after Holm correction and with a significant interaction test.
* **Don't ship** otherwise, or if a guardrail fails.
