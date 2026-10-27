import sqlite3
import numpy as np

DB_PATH = "data/experiment.db"
EXPERIMENT_ID = "checkout_one_page_v1"
N_BOOTSTRAPS = 5000

rng = np.random.default_rng(42)

query = """
WITH variant_counts AS (
    SELECT user_id, COUNT(DISTINCT variant) AS variants
    FROM assignments
    WHERE experiment_id = ?
    GROUP BY user_id
),
cohort AS (
    SELECT a.user_id, a.variant,
           MIN(a.assigned_ts) AS assigned_ts
    FROM assignments a
    JOIN variant_counts v ON v.user_id = a.user_id
    JOIN users u ON u.user_id = a.user_id
    WHERE a.experiment_id = ?
      AND v.variants = 1
      AND u.is_bot = 0
    GROUP BY a.user_id, a.variant
)
SELECT c.user_id, c.variant,
       COALESCE(SUM(o.revenue_usd), 0) AS revenue
FROM cohort c
LEFT JOIN orders o
    ON o.user_id = c.user_id
   AND o.order_ts >= c.assigned_ts
   AND o.order_ts < datetime(c.assigned_ts, '+72 hours')
GROUP BY c.user_id, c.variant
"""

with sqlite3.connect(DB_PATH) as conn:
    rows = conn.execute(
        query, (EXPERIMENT_ID, EXPERIMENT_ID)
    ).fetchall()

control = np.array(
    [r[2] for r in rows if r[1] == "control"],
    dtype=float
)
treatment = np.array(
    [r[2] for r in rows if r[1] == "treatment"],
    dtype=float
)

observed_difference = treatment.mean() - control.mean()

bootstrap_differences = np.empty(N_BOOTSTRAPS)

for i in range(N_BOOTSTRAPS):
    sampled_control = rng.choice(
        control, size=len(control), replace=True
    )
    sampled_treatment = rng.choice(
        treatment, size=len(treatment), replace=True
    )

    bootstrap_differences[i] = (
        sampled_treatment.mean() - sampled_control.mean()
    )

ci_low, ci_high = np.percentile(
    bootstrap_differences, [2.5, 97.5]
)

print("=" * 55)
print("BOOTSTRAP REVENUE VALIDATION")
print("=" * 55)
print(f"Bootstrap iterations: {N_BOOTSTRAPS:,}")
print(f"Control users: {len(control):,}")
print(f"Treatment users: {len(treatment):,}")
print(f"Observed revenue difference: ${observed_difference:.4f}")
print(f"Bootstrap 95% CI: [${ci_low:.4f}, ${ci_high:.4f}]")

if ci_low > 0:
    print("Interpretation: The bootstrap CI is entirely above zero.")
elif ci_high < 0:
    print("Interpretation: The bootstrap CI is entirely below zero.")
else:
    print("Interpretation: The bootstrap CI includes zero.")

print("Note: This interval does not resolve possible experiment")
print("design, assignment, or cohort-selection biases.")
