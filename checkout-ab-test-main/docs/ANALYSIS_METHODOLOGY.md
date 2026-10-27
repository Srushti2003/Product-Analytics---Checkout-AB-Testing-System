# Analysis Methodology

## 1. Objective

The objective of this project is to evaluate the observed performance of two checkout experiment variants:

- **Control:** The baseline experience.
- **Treatment:** The alternative checkout experience.

The analysis compares conversion and revenue-related metrics to understand whether the treatment group performed differently from the control group.

The dataset is simulated. The findings demonstrate an analytical workflow and should not be presented as verified results from a real production experiment.

## 2. Data Sources and Structure

The analysis uses a SQLite database containing four tables.

| Table | Purpose |
|---|---|
| `users` | User information, including signup timestamp, platform, country, and bot indicator |
| `assignments` | Experiment assignments, including user ID, experiment ID, variant, and assignment timestamp |
| `sessions` | User session identifiers and session timestamps |
| `orders` | Order identifiers, user IDs, order timestamps, revenue, and refund flags |

The experiment analyzed is `checkout_one_page_v1`.

The available data does not contain dedicated product-view, cart, or payment-step events. Therefore, this project does not calculate a detailed checkout funnel for those stages.

## 3. Data Quality Assessment

Before calculating experiment metrics, the data was inspected for record consistency, assignment issues, date coverage, and bot distribution.

### Key findings

- Total users: 61,800.
- Distinct users with an assignment for the selected experiment: 61,800.
- Repeated user-experiment assignment groups: 1,163.
- Users assigned to multiple variants: 240.
- Bots identified in the user table: 1,800.
- Orders without a matching user record: 0.
- Sessions without a matching user record: 0.

The assignment table contains repeated records. These were investigated before analysis rather than assuming every assignment row represented a unique user.

The bot distribution was also uneven across variants. This is an important data-quality concern because bot activity may affect conversion and revenue metrics.

## 4. Cohort Definition and Eligibility Rules

The analytical cohort was constructed using the following rules:

1. Select assignments for experiment `checkout_one_page_v1`.
2. Exclude users marked as bots (`is_bot = 1`).
3. Exclude users appearing in both control and treatment variants.
4. For repeated assignments to the same variant, retain the earliest assignment timestamp.
5. Use the earliest retained assignment timestamp as the start of the outcome window.

After these rules were applied, the analysis contained 59,760 eligible users:

| Variant | Eligible users |
|---|---:|
| Control | 29,790 |
| Treatment | 29,970 |
| Total | 59,760 |

**Interpretation caution:** Excluding users who appeared in both variants may introduce selection bias. The original assignment mechanism and experiment protocol have not been independently verified, so these eligibility rules should be treated as analytical decisions rather than confirmed experimental design rules.

## 5. Conversion Metric

### Definition

A user is considered converted if they placed at least one order during the 72-hour window following their retained assignment timestamp.

The order timestamp must satisfy:

`order_ts >= assigned_ts`

and

`order_ts < assigned_ts + 72 hours`

Orders placed before assignment are not counted as post-assignment conversions. A user with multiple qualifying orders is counted once in the user-level conversion metric.

### Formula

Conversion rate is calculated as:

`Conversion Rate = Converted Eligible Users / Total Eligible Users`

### Observed results

| Metric | Control | Treatment |
|---|---:|---:|
| Eligible users | 29,790 | 29,970 |
| Converted users | 2,301 | 2,760 |
| Conversion rate | 7.72% | 9.21% |
| Orders within 72 hours | 2,455 | 2,944 |

The observed absolute conversion-rate difference was approximately **+1.49 percentage points**.

The observed relative conversion lift was approximately **+19.23%**, calculated relative to the control conversion rate.

## 6. Conversion Statistical Test

A two-proportion z-test was used to compare the conversion rates of the control and treatment cohorts.

- **Null hypothesis (H₀):** The population conversion rates are equal.
- **Alternative hypothesis (H₁):** The population conversion rates are different.
- **Significance level:** 0.05.
- **Confidence interval:** 95%.

### Results

- Z-statistic: approximately 6.52.
- P-value: approximately 7.03 × 10⁻¹¹.
- 95% confidence interval for the absolute conversion-rate difference: approximately +1.04 to +1.93 percentage points.

The p-value is below 0.05, so the null hypothesis is rejected under the assumptions of this test. The analyzed cohorts show a statistically significant difference in conversion rates.

Statistical significance alone does not establish that the treatment caused the difference. That conclusion requires confidence in the assignment process, experimental design, cohort selection, and test assumptions.

## 7. Revenue Analysis

Revenue was analyzed using the eligible user cohorts and orders associated with each variant.

Metrics included:

- Recorded revenue.
- Revenue associated with orders flagged as refunded.
- Revenue excluding flagged-refund amounts, treated as provisional.
- Revenue per eligible user.
- Average order value.
- Order refund rate.

### Observed results

| Metric | Control | Treatment |
|---|---:|---:|
| Recorded revenue | $166,292.50 | $195,297.96 |
| Revenue excluding flagged-refund amounts | $156,375.47 | $184,242.07 |
| Revenue per eligible user | $5.58 | $6.52 |
| Average order value | $67.74 | $66.34 |
| Flagged refunded orders | 152 | 178 |
| Order refund rate | 6.19% | 6.05% |

Revenue excluding flagged-refund amounts is provisional. The dataset's refund flag does not, by itself, establish whether a refund was full or partial, when it occurred, or whether the recorded revenue already reflects it.

Revenue per eligible user is calculated using the eligible user count for each variant. The revenue analysis should use consistent cohort and time-window rules when making comparisons.

## 8. Revenue Statistical Tests

### Welch two-sample t-test

A Welch two-sample t-test was used to compare mean revenue per eligible user between the variants. This test does not assume equal population variances.

Observed results:

- Control mean revenue per eligible user: approximately $5.58.
- Treatment mean revenue per eligible user: approximately $6.52.
- Observed difference: approximately $0.93 per eligible user.
- Relative difference: approximately +16.74%.
- 95% confidence interval for the mean difference: approximately $0.55 to $1.32.
- P-value: approximately 2.31 × 10⁻⁶.

### Bootstrap confidence interval

A bootstrap analysis using 5,000 resamples estimated the confidence interval for the difference in mean revenue per eligible user.

- Observed difference: approximately $0.93.
- Bootstrap 95% confidence interval: approximately $0.56 to $1.34.

Both intervals are above zero, supporting an observed positive difference in mean revenue per eligible user under the current cohort definitions.

These tests do not resolve possible bias from assignment issues, cohort exclusions, or the simulated nature of the dataset.

## 9. Limitations

1. **Simulated data:** Results do not establish expected business outcomes in a real checkout system.
2. **Unverified randomization:** The original experiment assignment mechanism has not been confirmed.
3. **Repeated assignments:** Some users have multiple assignment records.
4. **Cross-variant assignments:** Some users appear in both variants; excluding them can introduce selection bias.
5. **Bot imbalance:** Bot counts differ between variants.
6. **Outcome-window choice:** The 72-hour window is an analytical definition, not a confirmed original protocol.
7. **Refund semantics:** The refund flag and its relationship to recorded revenue require further verification.
8. **No detailed checkout events:** Product views, cart activity, and payment-step events are not available in the current tables.
9. **Causal interpretation:** Statistical significance is not sufficient to prove a causal treatment effect.

## 10. Next Steps

- Verify the original assignment mechanism and experiment protocol if this information is available.
- Investigate repeated and cross-variant assignments.
- Examine the impact of the uneven bot distribution.
- Confirm refund definitions and revenue treatment.
- Perform sensitivity analyses using alternative reasonable cohort and outcome-window definitions.
- Build a Power BI dashboard using the exported user-level and variant-level CSV files.

## 11. Conclusion

Under the current analytical rules, the treatment cohort has a higher observed 72-hour conversion rate and higher mean revenue per eligible user than the control cohort. The differences are statistically significant under the tests performed.

These results should be reported as findings from the analyzed simulated dataset, not as proof that the treatment would cause the same improvement in a real business environment.
