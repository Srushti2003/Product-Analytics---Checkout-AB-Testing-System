# Product Analytics & Checkout A/B Testing System

An end-to-end product analytics project that evaluates checkout experiment performance using SQL, Python, statistical hypothesis testing, and Power BI. The project compares conversion rates, revenue performance, average order value, and refund rates between control and treatment groups.

The project builds upon an existing open-source checkout A/B testing dataset and analysis repository, with additional data validation, conversion and revenue analysis, statistical testing, CSV exports, and an interactive Power BI dashboard.

## Table of Contents

- [Project Overview](#project-overview)
- [Dataset Source and Attribution](#dataset-source-and-attribution)
- [Business Objectives](#business-objectives)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Database Overview](#database-overview)
- [Methodology](#methodology)
- [Key Results](#key-results)
- [Power BI Dashboard](#power-bi-dashboard)
- [Data Quality and Limitations](#data-quality-and-limitations)
- [Installation and Execution](#installation-and-execution)
- [Documentation](#documentation)
- [Future Improvements](#future-improvements)

## Project Overview

E-commerce businesses continuously evaluate changes to their checkout experience to understand whether they improve customer conversion and business performance.

This project analyzes the experiment `checkout_one_page_v1` to compare the control and treatment groups using a defined 72-hour post-assignment conversion window.

The workflow covers database inspection, data quality validation, cohort construction, metric calculation, statistical hypothesis testing, revenue analysis, and interactive Power BI reporting.

**Project type:** Product Analytics, Experimentation and A/B Testing

**Dataset:** Simulated checkout experiment data

**Primary tools:** SQL, Python, SQLite, Power BI and DAX

## Dataset Source and Attribution

This project uses the dataset and foundational repository from:

**Original GitHub repository:** [oscar-palomo/checkout-ab-test](https://github.com/oscar-palomo/checkout-ab-test)

The dataset folder and existing project resources were obtained from this repository and used as the starting point for my work.

Based on this dataset, I extended the analysis with additional Python scripts, data quality investigations, a defined 72-hour conversion analysis, statistical tests for conversion and revenue metrics, Power BI CSV exports, and an interactive dashboard.

The original repository's scripts, SQL resources, analysis artifacts, and documentation are retained as part of the project structure.

**Attribution note:** The original repository and dataset are credited to their respective author. Please refer to the original repository's license and usage terms when reusing or redistributing its files.

## Business Objectives

- Compare checkout conversion rates between control and treatment groups.
- Calculate absolute conversion lift and relative conversion lift.
- Evaluate the statistical significance of the observed conversion-rate difference.
- Compare recorded revenue and revenue per eligible user.
- Analyze average order value and order refund rates.
- Investigate data quality issues that may affect experiment interpretation.
- Present the findings through an interactive Power BI dashboard.

## Technology Stack

| Technology | Purpose |
|---|---|
| SQL | Data inspection, cohort construction, filtering, joins and metric analysis |
| SQLite | Relational storage of experiment data |
| Python | Data validation, analysis automation and statistical testing |
| Pandas | Data manipulation and CSV exports |
| NumPy | Numerical calculations and bootstrap resampling |
| SciPy | Statistical hypothesis testing |
| Power BI | Interactive dashboards and visual analytics |
| DAX | Dashboard measures and calculations |
| Git and GitHub | Version control and project publication |

## Project Structure

The following structure represents the project organization used for this analysis.

```text
Product Analytics & Checkout AB Testing System/
│
├── checkout-ab-test-main/
│   ├── data/
│   │   ├── experiment.db
│   │   └── ground_truth.json
│   │
│   ├── docs/
│   │   ├── ANALYSIS_METHODOLOGY.md
│   │   ├── COMMAND_LOG.md
│   │   └── experiment_plan.md
│   │
│   ├── reports/
│   │   ├── figures/
│   │   │   ├── 01_primary_result.png
│   │   │   ├── 02_segments.png
│   │   │   ├── 03_novelty.png
│   │   │   ├── 04_aa_test.png
│   │   │   └── 05_peeking.png
│   │   ├── results.json
│   │   ├── summary.md
│   │   └── validation.json
│   │
│   ├── scripts/
│   │   ├── build_db.py
│   │   ├── run_analysis.py
│   │   └── validate.py
│   │
│   ├── sql/
│   │   ├── 00_schema.sql
│   │   ├── 01_clean_assignments.sql
│   │   ├── 02_data_quality.sql
│   │   ├── 03_srm_counts.sql
│   │   ├── 04_user_metrics.sql
│   │   ├── 05_guardrails.sql
│   │   └── 06_daily_cohorts.sql
│   │
│   ├── src/
│   │   └── abtest/
│   │       ├── __init__.py
│   │       ├── bayes.py
│   │       ├── plots.py
│   │       ├── power.py
│   │       ├── simulate.py
│   │       └── stats.py
│   │
│   ├── tests/
│   │   └── test_stats.py
│   │
│   ├── analyze_ab_test.py
│   ├── bootstrap_revenue_test.py
│   ├── check_database.py
│   ├── check_dates.py
│   ├── export_powerbi.py
│   ├── inspect_assignments.py
│   ├── revenue_analysis.py
│   ├── revenue_statistical_test.py
│   ├── statistical_test.py
│   ├── validate_data.py
│   │
│   ├── experiment_user_metrics.csv
│   ├── experiment_variant_summary.csv
│   ├── requirements.txt
│   └── README.md
│
├── power bi/
│   ├── Product Analytics & Checkout AB Testing Dashboard.pbix
│   └── background.avif
│
└── Commands and Scripts.docx
```

## Database Overview

The SQLite database contains four primary tables.

| Table | Description |
|---|---|
| `users` | User information, signup timestamps, platform, country and bot indicator |
| `assignments` | Experiment identifiers, user assignments, variants and assignment timestamps |
| `sessions` | User session identifiers and session timestamps |
| `orders` | Order identifiers, order timestamps, revenue and refund flags |

The selected experiment is `checkout_one_page_v1`.

The available data does not include dedicated product-view, cart, or payment-step events. Consequently, this project does not claim to measure those individual funnel stages.

## Methodology

### 1. Database Inspection and Data Quality

The database was inspected to understand its schema, row counts, relationships, timestamps, and assignment patterns.

Key findings included:

- 61,800 total users.
- 1,163 repeated user-experiment assignment groups.
- 240 users appearing in both control and treatment variants.
- 1,800 bot-flagged users.
- No unmatched user records for orders or sessions.

The analysis also identified an imbalance in the distribution of bot-flagged users across the variants, making assignment validation important before drawing business conclusions.

### 2. Cohort Construction

The additional conversion and revenue analysis uses the following eligibility rules:

1. Select assignments for `checkout_one_page_v1`.
2. Exclude users flagged as bots.
3. Exclude users assigned to both variants.
4. Collapse repeated assignments to the same variant by retaining the earliest assignment timestamp.
5. Count qualifying orders during the 72-hour period following that timestamp.

This produces an analytical population of 59,760 eligible users.

| Variant | Eligible users |
|---|---:|
| Control | 29,790 |
| Treatment | 29,970 |
| Total | 59,760 |

These rules define the cohort used in the additional analysis. They have not been independently verified as the original experiment protocol.

### 3. Conversion Analysis

A user is classified as converted if they placed at least one qualifying order within 72 hours after their retained assignment timestamp.

The conversion rate is calculated as:

`Conversion Rate = Converted Users / Eligible Users`

The analysis evaluates eligible users, converted users, conversion rates, absolute conversion lift, and relative conversion lift.

### 4. Statistical Testing

A two-proportion z-test was used to compare control and treatment conversion rates.

The analysis reports the z-statistic, p-value, absolute conversion-rate difference, relative lift, and 95% confidence interval.

For revenue per eligible user, the analysis also uses a Welch two-sample t-test and a bootstrap procedure with 5,000 resamples to estimate uncertainty in the difference between group means.

### 5. Revenue and Quality Analysis

The revenue analysis evaluates:

- Total recorded revenue
- Revenue per eligible user
- Average order value
- Flagged refunded orders
- Order refund rate
- Revenue excluding flagged-refund amounts

Revenue excluding flagged-refund amounts is treated as provisional because the dataset does not establish whether the refund flag represents a full or partial refund, when the refund occurred, or whether the recorded revenue already accounts for refunds.

### 6. Visualization and Reporting

The analysis exports user-level and variant-level CSV files for Power BI.

The dashboard uses a shared variant dimension to support consistent filtering across the report's user-level and summary-level tables.

## Key Results

The following results come from the additional 72-hour conversion and revenue analysis.

### Conversion Performance

| Metric | Control | Treatment |
|---|---:|---:|
| Eligible users | 29,790 | 29,970 |
| Converted users | 2,301 | 2,760 |
| Conversion rate | 7.72% | 9.21% |
| Orders within 72 hours | 2,455 | 2,944 |

The treatment group had an observed conversion rate approximately **1.49 percentage points higher** than the control group, equivalent to a relative lift of approximately **19.23%**.

### Conversion Statistical Results

| Metric | Result |
|---|---:|
| Z-statistic | 6.52 |
| P-value | 7.03 × 10⁻¹¹ |
| 95% confidence interval for absolute lift | +1.04 to +1.93 percentage points |
| Significance level | 0.05 |

The observed conversion-rate difference is statistically significant under the assumptions of the two-proportion z-test.

### Revenue Performance

| Metric | Control | Treatment |
|---|---:|---:|
| Recorded revenue | $166,292.50 | $195,297.96 |
| Revenue per eligible user | $5.58 | $6.52 |
| Average order value | $67.74 | $66.34 |
| Flagged refunded orders | 152 | 178 |
| Order refund rate | 6.19% | 6.05% |
| Revenue excluding flagged-refund amounts | $156,375.47 | $184,242.07 |

The observed mean revenue per eligible user was approximately $0.93 higher in the treatment group. The Welch test and bootstrap analysis both produced 95% confidence intervals above zero under the current cohort definitions.

Average order value was slightly lower in the treatment group, while the observed order refund rate was also slightly lower.

These are descriptive findings from the analyzed simulated dataset and are not verified outcomes from a production checkout system.

## Power BI Dashboard

The Power BI report is located in the `power bi/` directory.

**Dashboard file:** `Product Analytics & Checkout AB Testing Dashboard.pbix`

### Page 1 — Experiment Overview

- Eligible user and conversion KPI cards
- Conversion-rate comparison between control and treatment
- Total revenue comparison
- Revenue per eligible user
- Absolute and relative conversion lift
- P-value and confidence interval
- Variant slicer

### Page 2 — Revenue & Quality Analysis

- Average order value comparison
- Order refund-rate comparison
- Revenue excluding flagged refunds
- Business interpretation of revenue and quality metrics

The dashboard's displayed figures were checked against the Python analysis results.

## Data Quality and Limitations

Several limitations should be considered when interpreting the results:

- **Simulated dataset:** Findings do not establish expected results for a real e-commerce business.
- **Assignment integrity:** The original randomization mechanism has not been independently verified.
- **Repeated assignments:** Duplicate assignment records required investigation and deduplication.
- **Cross-variant assignments:** Excluding users who appeared in both variants may introduce selection bias.
- **Bot imbalance:** Bot-flagged users were unevenly distributed across variants.
- **Outcome-window definition:** The 72-hour conversion window is an analytical choice, not a confirmed original protocol.
- **Refund definitions:** The meaning and timing of the refund flag remain unverified.
- **Causal interpretation:** Statistical significance alone does not establish a causal treatment effect.

These issues should be investigated before using the results to make a production rollout decision.

## Installation and Execution

### Prerequisites

- Python
- Power BI Desktop
- Git (optional, for version control)

### 1. Navigate to the project directory

Run commands from the `checkout-ab-test-main/` directory.

```powershell
cd "path\to\Product Analytics & Checkout AB Testing System\checkout-ab-test-main"
```

Replace the example path with your actual local project location.

### 2. Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 4. Inspect and validate the database

```powershell
python .\check_database.py
python .\validate_data.py
python .\inspect_assignments.py
python .\check_dates.py
```

### 5. Run the conversion and statistical analyses

```powershell
python .\analyze_ab_test.py
python .\statistical_test.py
```

### 6. Run the revenue analyses

```powershell
python .\revenue_analysis.py
python .\revenue_statistical_test.py
python .\bootstrap_revenue_test.py
```

### 7. Export the Power BI datasets

```powershell
python .\export_powerbi.py
```

The script generates:

- `experiment_user_metrics.csv`
- `experiment_variant_summary.csv`

Import these files into Power BI Desktop to build or refresh the dashboard.

The project also retains the original repository's database-building, analysis, validation, and SQL resources. Their workflows are separate from the additional scripts above; use their respective documentation when running those workflows.

## Documentation

Supporting documentation is available in the `docs/` directory:

- `ANALYSIS_METHODOLOGY.md` — cohort definitions, analytical assumptions, and metric methodology.
- `COMMAND_LOG.md` — commands used during project development.
- `experiment_plan.md` — experiment planning documentation inherited from the project resources.

`Commands and Scripts.docx` provides additional command and script documentation at the root of the project.

## Future Improvements

- Validate the original experiment randomization and sample-ratio expectations.
- Investigate the impact of cross-variant assignments and repeated assignments.
- Perform sensitivity analyses using alternative cohort and outcome-window definitions.
- Confirm refund semantics and timing.
- Expand automated unit and data validation tests.
- Automate the analytical reporting workflow and dashboard refresh.
- Explore additional user segments when supported by the data and a suitable analysis plan.

## Conclusion

This project demonstrates an end-to-end product analytics workflow using an existing checkout experiment dataset as the foundation for additional data analysis and visualization work.

The additional analysis indicates higher observed conversion and mean revenue per eligible user in the treatment group under the current cohort rules. Statistical tests indicate differences between the analyzed groups, but the simulated data and unresolved assignment issues limit causal interpretation.

The project emphasizes the importance of data quality, clearly defined metrics, statistical testing, and transparent communication when evaluating product experiments.
