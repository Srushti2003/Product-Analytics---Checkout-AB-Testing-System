# Command Log

## 1. Project Overview

This document records the main commands used to set up, inspect, validate, analyze, and export data for the Product Analytics & Checkout A/B Testing System.

**Environment:** Windows PowerShell  
**Programming language:** Python  
**Database:** SQLite  
**Experiment ID:** `checkout_one_page_v1`

The commands below describe the intended reproducible workflow. Exploratory commands that failed during development are not included unless they are necessary for troubleshooting.

## 2. Environment Setup

Check the installed Python version:

```powershell
python --version
```

Create a virtual environment:

```powershell
python -m venv .venv
```

Activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Upgrade pip:

```powershell
python -m pip install --upgrade pip
```

If the project contains a `requirements.txt` file, install the dependencies:

```powershell
python -m pip install -r requirements.txt
```

## 3. Build the Database

Run the provided database-building script:

```powershell
python .\scripts\build_db.py
```

The script builds the SQLite database used for the analysis. The database file is expected at:

```text
data/experiment.db
```

## 4. Database Inspection

Run the custom database inspection script:

```powershell
python .\check_database.py
```

Purpose:
- List the database tables.
- Inspect table schemas and column names.
- Check row counts.
- Display sample records.

## 5. Data Quality Validation

Run the data validation script:

```powershell
python .\validate_data.py
```

Purpose:
- Inspect data quality.
- Check for missing or inconsistent records.
- Validate relationships between users, sessions, orders, and experiment assignments.

Inspect experiment assignments:

```powershell
python .\inspect_assignments.py
```

Purpose:
- Identify repeated assignments.
- Check users assigned to multiple variants.
- Inspect orders that occurred before experiment assignment.

Inspect dates and bot distribution:

```powershell
python .\check_dates.py
```

Purpose:
- Review the date ranges of the datasets.
- Compare bot counts across experiment variants.
- Check whether the available data covers the selected outcome window.

## 6. Conversion Analysis

Run the conversion analysis:

```powershell
python .\analyze_ab_test.py
```

The analysis uses a 72-hour post-assignment conversion window under the current analytical definition.

Run the statistical significance test:

```powershell
python .\statistical_test.py
```

Purpose:
- Compare conversion rates between control and treatment.
- Calculate the absolute conversion-rate difference.
- Calculate relative lift.
- Perform a two-proportion z-test.
- Calculate a 95% confidence interval for the absolute difference.

## 7. Revenue Analysis

Run the revenue analysis:

```powershell
python .\revenue_analysis.py
```

Purpose:
- Compare recorded revenue across variants.
- Calculate revenue per eligible user and average order value.
- Inspect flagged refunds and the order refund rate.

Run the Welch two-sample t-test:

```powershell
python .\revenue_statistical_test.py
```

Run the bootstrap revenue comparison:

```powershell
python .\bootstrap_revenue_test.py
```

The bootstrap script uses 5,000 resamples to estimate a confidence interval for the difference in mean revenue per eligible user.

## 8. Export Data for Power BI

Run the export script:

```powershell
python .\export_powerbi.py
```

The script generates the following files for dashboard development:

- `experiment_user_metrics.csv`
- `experiment_variant_summary.csv`

The CSV files provide user-level metrics and a variant-level summary for use in Power BI.

## 9. Reproduction Order

To reproduce the analysis, use this sequence after setting up the environment and ensuring the required source data and dependencies are available:

1. Build the database, if it does not already exist.
2. Inspect the database structure and records.
3. Run data quality validation.
4. Inspect experiment assignments.
5. Review date ranges and bot distribution.
6. Run conversion analysis.
7. Run the conversion statistical test.
8. Run revenue analysis.
9. Run the Welch t-test and bootstrap analysis.
10. Export the CSV files for Power BI.

Run commands from the project root directory.

## 10. Notes

- The analysis is based on a simulated dataset.
- The 72-hour conversion window is an analytical choice made for this project; it has not been confirmed as the experiment's original protocol.
- The statistical results describe the analyzed cohorts and should not automatically be interpreted as proof of a causal treatment effect.
- Refund-adjusted revenue is provisional because the exact meaning and timing of the refund flag have not been confirmed.
- The Power BI dashboard is a planned next step; the CSV exports have been generated for it.
