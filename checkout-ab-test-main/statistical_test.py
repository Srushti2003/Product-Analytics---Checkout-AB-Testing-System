from math import sqrt
from scipy.stats import norm

# Results from the SQL analysis
control_users = 29790
control_converted = 2301

treatment_users = 29970
treatment_converted = 2760

# Conversion rates
p_control = control_converted / control_users
p_treatment = treatment_converted / treatment_users

# Effect sizes
absolute_lift = p_treatment - p_control
relative_lift = absolute_lift / p_control

# Two-proportion z-test using pooled standard error
pooled_rate = (
    control_converted + treatment_converted
) / (control_users + treatment_users)

standard_error_test = sqrt(
    pooled_rate * (1 - pooled_rate)
    * (1 / control_users + 1 / treatment_users)
)

z_score = absolute_lift / standard_error_test
p_value = 2 * norm.sf(abs(z_score))

# Approximate 95% confidence interval for absolute lift
standard_error_ci = sqrt(
    p_control * (1 - p_control) / control_users
    + p_treatment * (1 - p_treatment) / treatment_users
)

ci_lower = absolute_lift - 1.96 * standard_error_ci
ci_upper = absolute_lift + 1.96 * standard_error_ci

print("=" * 55)
print("A/B TEST STATISTICAL RESULTS")
print("=" * 55)

print(f"Control conversion rate:   {p_control:.4%}")
print(f"Treatment conversion rate: {p_treatment:.4%}")
print(f"Absolute lift:             {absolute_lift:.4%}")
print(f"Relative lift:             {relative_lift:.2%}")
print(f"Z-score:                  {z_score:.4f}")
print(f"P-value:                  {p_value:.3e}")
print(
    "95% CI for absolute lift: "
    f"[{ci_lower:.4%}, {ci_upper:.4%}]"
)

alpha = 0.05
print("\nStatistical test at alpha = 0.05:")

if p_value < alpha:
    print("Reject the null hypothesis.")
    print("The conversion rates differ statistically.")
else:
    print("Fail to reject the null hypothesis.")
    print("The evidence is insufficient to establish a difference.")

print("\nNote: The confidence interval is a normal approximation.")
print("Statistical significance does not establish causality.")
