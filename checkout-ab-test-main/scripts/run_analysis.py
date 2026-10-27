"""Run the full pre-registered analysis and write the report.

Usage:  python scripts/run_analysis.py
Outputs: reports/results.json, reports/summary.md, reports/figures/*.png
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from abtest import bayes, plots, power, stats  # noqa: E402
from abtest.plots import plt  # noqa: E402

SQL = ROOT / "sql"
FIG = ROOT / "reports" / "figures"
PLAN = {"baseline": 0.11, "rel_mde": 0.07, "alpha": 0.05, "power": 0.80}
CUPED_COVARIATES = ["pre_orders", "pre_sessions"]


def q(con, name: str) -> pd.DataFrame:
    return pd.read_sql((SQL / name).read_text(), con)


def split(df: pd.DataFrame, col: str):
    return df.loc[df.variant == "control", col].to_numpy(), df.loc[df.variant == "treatment", col].to_numpy()


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(ROOT / "data" / "experiment.db")
    con.executescript((SQL / "01_clean_assignments.sql").read_text())

    out: dict = {"plan": PLAN}

    # ------------------------------------------------------------------ #
    # 1. Data quality + SRM
    # ------------------------------------------------------------------ #
    funnel = q(con, "02_data_quality.sql")
    srm_counts = q(con, "03_srm_counts.sql").pivot(index="population", columns="variant", values="users")
    out["data_quality"] = funnel.to_dict(orient="records")
    out["srm"] = {
        pop: stats.srm_test(int(row["control"]), int(row["treatment"]))
        for pop, row in srm_counts.iterrows()
    }
    clean_srm = out["srm"]["clean (analysis population)"]
    if clean_srm["srm_detected"]:
        raise SystemExit("SRM in the clean population: stop and debug before reading results.")

    m = q(con, "04_user_metrics.sql")
    is_t = (m.variant == "treatment").to_numpy()
    n_c, n_t = int((~is_t).sum()), int(is_t.sum())

    # ------------------------------------------------------------------ #
    # 2. Primary metric: conversion
    # ------------------------------------------------------------------ #
    yc, yt = split(m, "converted")
    raw = stats.diff_in_means(yc, yt)
    cup = stats.cuped_test(m.converted.to_numpy(), m[CUPED_COVARIATES].to_numpy(), is_t)
    bay = bayes.beta_binomial_readout(int(yc.sum()), n_c, int(yt.sum()), n_t)
    bay.pop("lift_draws")
    out["primary"] = {"raw": raw, "cuped": cup, "bayes": bay}
    out["power"] = {
        "planned_n_per_arm": power.sample_size_per_arm(PLAN["baseline"], PLAN["rel_mde"]),
        "achieved_n_per_arm": [n_c, n_t],
        "achieved_mde_raw": power.mde_for_sample(raw["control_mean"], min(n_c, n_t)),
        "achieved_mde_cuped": power.mde_for_sample(
            raw["control_mean"], min(n_c, n_t), variance_reduction=cup["variance_reduction"]
        ),
    }

    # ------------------------------------------------------------------ #
    # 3. Secondary: revenue per user (heavy tailed -> bootstrap as well)
    # ------------------------------------------------------------------ #
    rc, rt = split(m, "revenue")
    rpu = stats.diff_in_means(rc, rt)
    rpu_cuped = stats.cuped_test(m.revenue.to_numpy(), m[["pre_revenue", "pre_orders", "pre_sessions"]].to_numpy(), is_t)
    rpu_boot = stats.bootstrap_rel_lift(rc, rt, n_boot=5_000, seed=1)
    out["secondary_rpu"] = {"raw": rpu, "cuped": rpu_cuped, "bootstrap": rpu_boot}

    # ------------------------------------------------------------------ #
    # 4. Guardrails (per-order ratio metrics, clustered by user)
    # ------------------------------------------------------------------ #
    mc_, mt_ = m[~is_t], m[is_t]
    aov = stats.ratio_metric_test(mc_.revenue, mc_.orders, mt_.revenue, mt_.orders)
    refund = stats.ratio_metric_test(mc_.refunded_orders, mc_.orders, mt_.refunded_orders, mt_.orders)
    out["guardrails"] = {
        # Guardrail fails on a statistically significant decline (plan: 95% CI entirely below 0)
        "avg_order_value": {**aov, "pass": not (aov["abs_ci"][1] < 0)},
        "refund_rate": {**refund, "pass": not (refund["p_value"] < 0.05 and refund["abs_diff"] > 0)},
        "sql_check": q(con, "05_guardrails.sql").to_dict(orient="records"),
    }

    # ------------------------------------------------------------------ #
    # 5. Pre-registered segments (CUPED within segment, Holm-corrected)
    # ------------------------------------------------------------------ #
    segs = {}
    for col, levels in [("platform", ["mobile", "desktop"]), ("user_type", ["new", "returning"])]:
        for lvl in levels:
            s = m[m[col] == lvl]
            st = (s.variant == "treatment").to_numpy()
            segs[f"{col}={lvl}"] = stats.cuped_test(s.converted.to_numpy(), s[CUPED_COVARIATES].to_numpy(), st)
    holm = stats.holm_adjust([r["p_value"] for r in segs.values()])
    for (k, r), p_adj in zip(segs.items(), holm):
        r["p_holm"] = p_adj
    out["segments"] = segs
    out["interactions"] = {
        "platform": stats.interaction_test(segs["platform=mobile"], segs["platform=desktop"]),
        "user_type": stats.interaction_test(segs["user_type=returning"], segs["user_type=new"]),
    }

    # ------------------------------------------------------------------ #
    # 6. Novelty: lift by enrollment cohort
    # ------------------------------------------------------------------ #
    daily = q(con, "06_daily_cohorts.sql")
    wide = daily.pivot_table(index=["assigned_date", "user_type"], columns="variant", values=["users", "conversions"]).reset_index()
    wide.columns = ["date", "user_type", "conv_c", "conv_t", "n_c", "n_t"]
    pc, pt = wide.conv_c / wide.n_c, wide.conv_t / wide.n_t
    wide["abs_lift"] = pt - pc
    wide["se"] = np.sqrt(pc * (1 - pc) / wide.n_c + pt * (1 - pt) / wide.n_t)
    wide["day"] = pd.to_datetime(wide.date).dt.dayofyear - pd.Timestamp("2026-03-02").dayofyear
    novelty = {}
    for ut, g in wide.groupby("user_type"):
        w = 1 / g.se**2  # inverse-variance weighted linear trend of lift over enrollment day
        X = np.c_[np.ones(len(g)), g.day]
        W = np.diag(w)
        beta = np.linalg.solve(X.T @ W @ X, X.T @ W @ g.abs_lift)
        cov = np.linalg.inv(X.T @ W @ X)
        slope, se_slope = beta[1], np.sqrt(cov[1, 1])
        novelty[ut] = {
            "slope_pp_per_day": slope * 100,
            "slope_ci_pp": [(slope - 1.96 * se_slope) * 100, (slope + 1.96 * se_slope) * 100],
            "p_value": float(2 * norm.sf(abs(slope / se_slope))),
            "first_week_lift": float(np.average(g.abs_lift[g.day < 7], weights=w[g.day < 7])),
            "second_week_lift": float(np.average(g.abs_lift[g.day >= 7], weights=w[g.day >= 7])),
        }
    out["novelty"] = novelty

    # Long-run proxy: if novelty is present, the lift among late cohorts (who
    # arrive after the new checkout has been live for a week) is closer to
    # the steady-state effect than the headline number.
    late = m[m.assigned_date >= "2026-03-09"]
    lt = (late.variant == "treatment").to_numpy()
    out["late_cohorts"] = stats.cuped_test(late.converted.to_numpy(), late[CUPED_COVARIATES].to_numpy(), lt)

    # ------------------------------------------------------------------ #
    # Decision
    # ------------------------------------------------------------------ #
    primary_sig = cup["p_value"] < PLAN["alpha"] and cup["abs_diff"] > 0
    guard_ok = all(out["guardrails"][g]["pass"] for g in ["avg_order_value", "refund_rate"])
    out["decision"] = "SHIP" if (primary_sig and guard_ok) else ("HOLD: guardrail" if primary_sig else "DON'T SHIP")

    # ------------------------------------------------------------------ #
    # Figures
    # ------------------------------------------------------------------ #
    make_figures(out, wide)

    (ROOT / "reports" / "results.json").write_text(json.dumps(out, indent=2, default=float))
    write_summary(out)
    print((ROOT / "reports" / "summary.md").read_text())


# ---------------------------------------------------------------------- #
def make_figures(out: dict, wide: pd.DataFrame) -> None:
    raw, cup, bay = out["primary"]["raw"], out["primary"]["cuped"], out["primary"]["bayes"]
    late = out["late_cohorts"]

    # 01: headline estimate, three ways
    fig, ax = plt.subplots(figsize=(8, 3.6))
    plots.forest(
        ax,
        ["Two-proportion z-test", "CUPED-adjusted z-test", "Bayesian (Beta-Binomial)", "Late cohorts only (days 8–14)"],
        [raw["rel_lift"], cup["rel_lift"], bay["rel_lift_mean"], late["rel_lift"]],
        [raw["rel_ci"], cup["rel_ci"], bay["rel_lift_ci95"], late["rel_ci"]],
        colors=[plots.NEUTRAL, plots.BLUE, plots.ORANGE, plots.AQUA],
        annotate=[
            f"{plots.pct(raw['rel_lift'])}   {plots.fmt_p(raw['p_value'])}",
            f"{plots.pct(cup['rel_lift'])}   {plots.fmt_p(cup['p_value'])}",
            f"{plots.pct(bay['rel_lift_mean'])}   P(better) > 0.999",
            f"{plots.pct(late['rel_lift'])}   {plots.fmt_p(late['p_value'])}",
        ],
    )
    ax.axvline(out["plan"]["rel_mde"] * 100, color=plots.NEUTRAL, lw=1, ls=":", zorder=0)
    ax.text(out["plan"]["rel_mde"] * 100, -0.75, " planned MDE", color=plots.TEXT_2, fontsize=8.5, va="center")
    ax.set_xlabel("Relative lift in 7-day conversion (95% interval)")
    ax.set_title("One-page checkout lifts conversion")
    plots.subtitle(ax, f"n = {raw['n_control']:,} control / {raw['n_treatment']:,} treatment users")
    ax.set_ylim(-1.1, 3.5)
    plots.save(fig, FIG / "01_primary_result.png")

    # 02: segments
    segs = out["segments"]
    order = ["platform=mobile", "platform=desktop", "user_type=returning", "user_type=new"]
    labels = ["Mobile", "Desktop", "Returning users", "New users"]
    fig, ax = plt.subplots(figsize=(8, 3.3))
    plots.forest(
        ax, labels,
        [segs[k]["rel_lift"] for k in order],
        [segs[k]["rel_ci"] for k in order],
        colors=[plots.BLUE, plots.BLUE, plots.ORANGE, plots.ORANGE],
        annotate=[f"{plots.pct(segs[k]['rel_lift'])}   Holm {plots.fmt_p(segs[k]['p_holm'])}" for k in order],
    )
    ax.axhline(1.5, color=plots.GRID, lw=1)
    ax.set_xlabel("Relative lift in conversion, CUPED-adjusted (95% CI)")
    ax.set_title("The gain comes from mobile")
    ip = out["interactions"]["platform"]["p_value"]
    plots.subtitle(ax, f"Pre-registered segments  ·  mobile vs desktop difference: {plots.fmt_p(ip)}")
    plots.save(fig, FIG / "02_segments.png")

    # 03: novelty (small multiples)
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.3), sharey=True)
    for ax, ut, color in zip(axes, ["returning", "new"], [plots.ORANGE, plots.BLUE]):
        g = wide[wide.user_type == ut].sort_values("day")
        ax.errorbar(g.day + 1, g.abs_lift * 100, yerr=1.96 * g.se * 100, fmt="o", color=color,
                    ms=5, lw=1.4, capsize=0, mec=plots.SURFACE, mew=1.5)
        nv = out["novelty"][ut]
        xs = np.array([0, 13])
        b1 = nv["slope_pp_per_day"]
        # re-fit intercept for display with the same weights
        w = 1 / g.se**2
        b0 = np.average(g.abs_lift * 100 - b1 * g.day, weights=w)
        ax.plot(xs + 1, b0 + b1 * xs, color=color, lw=2)
        ax.axhline(0, color=plots.NEUTRAL, lw=1, ls="--")
        ax.set_title(f"{ut.capitalize()} users", fontsize=11.5, pad=20)
        ax.text(0.0, 1.025, f"trend {b1:+.2f} pp/day ({plots.fmt_p(nv['p_value'])})", transform=ax.transAxes,
                fontsize=9, color=plots.TEXT_2, va="bottom")
        ax.set_xlabel("Enrollment day")
        ax.set_xticks([1, 4, 7, 10, 14])
    axes[0].set_ylabel("Conversion lift (pp)")
    fig.suptitle("Returning users' lift fades as the new checkout stops being new",
                 x=0.01, ha="left", fontsize=13, fontweight="bold", color=plots.TEXT)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(FIG / "03_novelty.png", bbox_inches="tight")
    plt.close(fig)


def fp(p: float) -> str:
    return "<0.0001" if p < 0.0001 else f"{p:.4f}"


def write_summary(out: dict) -> None:
    p, c, b = out["primary"]["raw"], out["primary"]["cuped"], out["primary"]["bayes"]
    r = out["secondary_rpu"]
    g = out["guardrails"]
    srm = out["srm"]
    lines = [
        "# Results summary (auto-generated by scripts/run_analysis.py)",
        "",
        f"**Decision: {out['decision']}**",
        "",
        "## Sample ratio",
        "| Population | Control | Treatment | Treatment share | SRM p-value |",
        "|---|---:|---:|---:|---:|",
    ]
    for pop, s in srm.items():
        lines.append(f"| {pop} | {s['n_control']:,} | {s['n_treatment']:,} | {s['treatment_share']:.2%} | {s['p_value']:.2g} |")
    lines += [
        "",
        "## Primary: 7-day conversion",
        "| Method | Control | Treatment | Relative lift | 95% CI | p |",
        "|---|---:|---:|---:|---|---:|",
        f"| z-test | {p['control_mean']:.2%} | {p['treatment_mean']:.2%} | {p['rel_lift']:+.2%} | [{p['rel_ci'][0]:+.2%}, {p['rel_ci'][1]:+.2%}] | {fp(p['p_value'])} |",
        f"| CUPED | | | {c['rel_lift']:+.2%} | [{c['rel_ci'][0]:+.2%}, {c['rel_ci'][1]:+.2%}] | {fp(c['p_value'])} |",
        f"| Bayesian | | | {b['rel_lift_mean']:+.2%} | [{b['rel_lift_ci95'][0]:+.2%}, {b['rel_lift_ci95'][1]:+.2%}] | P(better) {'> 0.999' if b['prob_treatment_better'] > 0.999 else '= ' + format(b['prob_treatment_better'], '.3f')} |",
        "",
        f"CUPED variance reduction: {c['variance_reduction']:.1%} (CI {c['ci_width_reduction']:.1%} narrower). "
        f"Achieved MDE: {out['power']['achieved_mde_raw']:.2%} raw -> {out['power']['achieved_mde_cuped']:.2%} with CUPED.",
        "",
        f"Late cohorts only (enrolled days 8-14, long-run proxy): {out['late_cohorts']['rel_lift']:+.2%} "
        f"[{out['late_cohorts']['rel_ci'][0]:+.2%}, {out['late_cohorts']['rel_ci'][1]:+.2%}], p = {out['late_cohorts']['p_value']:.4f}",
        "",
        "## Secondary: revenue per user",
        f"- Control ${r['raw']['control_mean']:.2f} vs treatment ${r['raw']['treatment_mean']:.2f} "
        f"({r['raw']['rel_lift']:+.2%}, z-test p {fp(r['raw']['p_value'])})",
        f"- Bootstrap 95% CI: [{r['bootstrap']['rel_ci'][0]:+.2%}, {r['bootstrap']['rel_ci'][1]:+.2%}]",
        f"- CUPED: {r['cuped']['rel_lift']:+.2%} [{r['cuped']['rel_ci'][0]:+.2%}, {r['cuped']['rel_ci'][1]:+.2%}], "
        f"variance reduction {r['cuped']['variance_reduction']:.1%}",
        "",
        "## Guardrails",
        f"- Average order value: ${g['avg_order_value']['control']:.2f} -> ${g['avg_order_value']['treatment']:.2f} "
        f"({g['avg_order_value']['rel_lift']:+.2%}, CI [{g['avg_order_value']['rel_ci'][0]:+.2%}, {g['avg_order_value']['rel_ci'][1]:+.2%}]) "
        f"-> {'PASS' if g['avg_order_value']['pass'] else 'FAIL'}",
        f"- Refund rate: {g['refund_rate']['control']:.2%} -> {g['refund_rate']['treatment']:.2%} "
        f"(p = {g['refund_rate']['p_value']:.3f}) -> {'PASS' if g['refund_rate']['pass'] else 'FAIL'}",
        "",
        "## Segments (CUPED, Holm-corrected)",
        "| Segment | Control | Relative lift | 95% CI | p | Holm p |",
        "|---|---:|---:|---|---:|---:|",
    ]
    for k, s in out["segments"].items():
        lines.append(
            f"| {k} | {s['control_mean']:.2%} | {s['rel_lift']:+.2%} | [{s['rel_ci'][0]:+.2%}, {s['rel_ci'][1]:+.2%}] | {fp(s['p_value'])} | {fp(s['p_holm'])} |"
        )
    it = out["interactions"]
    lines += [
        "",
        f"Interaction tests: platform p: {fp(it['platform']['p_value'])}, user type p: {fp(it['user_type']['p_value'])}",
        "",
        "## Novelty (lift trend over enrollment days)",
    ]
    for ut, nv in out["novelty"].items():
        lines.append(
            f"- {ut}: {nv['slope_pp_per_day']:+.3f} pp/day (95% CI [{nv['slope_ci_pp'][0]:+.3f}, {nv['slope_ci_pp'][1]:+.3f}], p: {fp(nv['p_value'])}); "
            f"week 1 lift {nv['first_week_lift'] * 100:+.2f} pp, week 2 {nv['second_week_lift'] * 100:+.2f} pp"
        )
    (ROOT / "reports" / "summary.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
