import sqlite3
import numpy as np
from scipy import stats

DB_PATH = "data/experiment.db"
EXPERIMENT_ID = "checkout_one_page_v1"

connection = sqlite3.connect(DB_PATH)

query = """
WITH variant_counts AS (
    SELECT user_id, COUNT(DISTINCT variant) AS variants
    FROM assignments
    WHERE experiment_id = ?
    GROUP BY user_id
),
cohort AS (
    SELECT a.user_id, a.variant, MIN(a.assigned_ts) AS assigned_ts
    FROM assignments a
    JOIN variant_counts v ON v.user_id = a.user_id
    JOIN users u ON u.user_id = a.user_id
    WHERE a.experiment_id = ?
      AND v.variants = 1
      AND u.is_bot = 0
    GROUP BY a.user_id, a.variant
)
SELECT
    c.user_id,
    c.variant,
    COALESCE(SUM(o.revenue_usd), 0) AS revenue
FROM cohort c
LEFT JOIN orders o
  ON o.user_id = c.user_id
 AND o.order_ts >= c.assigned_ts
 AND o.order_ts < datetime(c.assigned_ts, '+72 hours')
GROUP BY c.user_id, c.variant
ORDER BY c.variant, c.user_id
"""

rows = connection.execute(
    query, (EXPERIMENT_ID, EXPERIMENT_ID)
).fetchall()
connection.close()

control = np.array(
    [r[2] for r in rows if r[1] == "control"], dtype=float
)
treatment = np.array(
    [r[2] for r in rows if r[1] == "treatment"], dtype=float
)

control_mean = control.mean()
treatment_mean = treatment.mean()
difference = treatment_mean - control_mean

test = stats.ttest_ind(treatment, control, equal_var=False)

# Welch confidence interval for treatment minus control
n_t, n_c = len(treatment), len(control)
v_t, v_c = treatment.var(ddof=1), control.var(ddof=1)

se = np.sqrt(v_t / n_t + v_c / n_c)

df = (v_t / n_t + v_c / n_c) ** 2 / (
    (v_t / n_t) ** 2 / (n_t - 1)
    + (v_c / n_c) ** 2 / (n_c - 1)
)

critical_value = stats.t.ppf(0.975, df)
ci_low = difference - critical_value * se
ci_high = difference + critical_value * se

relative_lift = difference / control_mean * 100

print("=" * 60)
print("USER-LEVEL REVENUE SIGNIFICANCE TEST")
print("=" * 60)
print(f"Control users: {n_c:,}")
print(f"Treatment users: {n_t:,}")
print(f"Control mean revenue/user: ${control_mean:.4f}")
print(f"Treatment mean revenue/user: ${treatment_mean:.4f}")
print(f"Difference per user: ${difference:.4f}")
print(f"Relative difference: {relative_lift:.2f}%")
print(f"95% CI for difference: [${ci_low:.4f}, ${ci_high:.4f}]")
print(f"Welch t-statistic: {test.statistic:.4f}")
print(f"Two-sided p-value: {test.pvalue:.6g}")

if test.pvalue < 0.05:
    print("Result: Statistically significant at alpha = 0.05.")
else:
    print("Result: Not statistically significant at alpha = 0.05.")

print("\nInterpret cautiously: assignment quality and experiment")
print("randomization have not yet been independently verified.")
