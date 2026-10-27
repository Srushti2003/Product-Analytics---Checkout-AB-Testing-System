"""Build the experiment warehouse: data/experiment.db (SQLite).

Takes the simulated users/sessions/orders and writes them out as raw event
tables, then adds the kinds of problems real tracking data has:

  * bot traffic (3% of assigned users) that lands in treatment more often
    because crawlers follow the new checkout URL
  * a logging bug: 0.4% of users get a second assignment event for the
    other arm
  * 1.5% of assignment events are duplicated

Usage:  python scripts/build_db.py
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from abtest.simulate import EXPERIMENT_START, ENROLL_DAYS, OUTCOME_DAYS, simulate_experiment  # noqa: E402

SEED = 42
N_HUMANS = 60_000
BOT_SHARE = 0.03
BOT_TREATMENT_SHARE = 0.70
CONFLICT_SHARE = 0.004
DUPLICATE_SHARE = 0.015


def to_ts(days: np.ndarray | pd.Series) -> pd.Series:
    ts = EXPERIMENT_START + pd.to_timedelta(np.asarray(days), unit="D")
    return pd.Series(ts).dt.strftime("%Y-%m-%d %H:%M:%S")


def main() -> None:
    rng = np.random.default_rng(SEED + 1)
    sim = simulate_experiment(n_users=N_HUMANS, seed=SEED)
    users, sessions, orders = sim["users"], sim["sessions"], sim["orders"]

    # ---- bots ----------------------------------------------------------------
    n_bots = int(N_HUMANS * BOT_SHARE)
    bot_ids = np.arange(N_HUMANS, N_HUMANS + n_bots)
    bot_assign = rng.uniform(0, ENROLL_DAYS, n_bots)
    bots = pd.DataFrame(
        {
            "user_id": bot_ids,
            "platform": rng.choice(["desktop", "mobile"], n_bots, p=[0.8, 0.2]),
            "country": rng.choice(["US", "CA", "UK", "DE"], n_bots),
            "variant": np.where(rng.random(n_bots) < BOT_TREATMENT_SHARE, "treatment", "control"),
            "assign_day": bot_assign,
        }
    )
    bot_k = rng.integers(20, 60, n_bots)
    bot_user = np.repeat(bot_ids, bot_k)
    bot_sessions = pd.DataFrame(
        {
            "user_id": bot_user,
            "day": np.repeat(bot_assign, bot_k) + rng.uniform(0, OUTCOME_DAYS, bot_user.size),
        }
    )

    all_users = pd.concat([users, bots], ignore_index=True)
    all_users["is_bot"] = (all_users["user_id"] >= N_HUMANS).astype(int)

    # Signup date: returning users signed up before the experiment
    pre_first = sessions[sessions["day"] < sessions["user_id"].map(users.set_index("user_id")["assign_day"]).fillna(np.inf)]
    first_seen = pre_first.groupby("user_id")["day"].min()
    signup_day = all_users["user_id"].map(first_seen)
    signup_day = signup_day.fillna(all_users["assign_day"]) - rng.uniform(0, 1 / 24, len(all_users))

    users_tbl = pd.DataFrame(
        {
            "user_id": all_users["user_id"],
            "signup_ts": to_ts(signup_day),
            "platform": all_users["platform"],
            "country": all_users["country"],
            "is_bot": all_users["is_bot"],
        }
    )

    # ---- assignment events (with a logging bug + duplicates) ----------------
    assign = pd.DataFrame(
        {
            "user_id": all_users["user_id"],
            "variant": all_users["variant"],
            "assign_day": all_users["assign_day"],
        }
    )
    human_ids = users["user_id"].to_numpy()
    conflict_ids = rng.choice(human_ids, int(N_HUMANS * CONFLICT_SHARE), replace=False)
    conflicts = assign[assign["user_id"].isin(conflict_ids)].copy()
    conflicts["variant"] = np.where(conflicts["variant"] == "control", "treatment", "control")
    conflicts["assign_day"] += rng.uniform(0.01, 2, len(conflicts))
    dup_idx = rng.choice(len(assign), int(len(assign) * DUPLICATE_SHARE), replace=False)
    duplicates = assign.iloc[dup_idx]
    assign_tbl = (
        pd.concat([assign, conflicts, duplicates], ignore_index=True)
        .sample(frac=1, random_state=SEED)
        .reset_index(drop=True)
    )
    assign_tbl = pd.DataFrame(
        {
            "user_id": assign_tbl["user_id"],
            "experiment_id": "checkout_one_page_v1",
            "variant": assign_tbl["variant"],
            "assigned_ts": to_ts(assign_tbl["assign_day"]),
        }
    )

    # ---- sessions & orders ---------------------------------------------------
    all_sessions = pd.concat([sessions, bot_sessions], ignore_index=True).sort_values(["user_id", "day"])
    sessions_tbl = pd.DataFrame(
        {
            "session_id": np.arange(1, len(all_sessions) + 1),
            "user_id": all_sessions["user_id"].to_numpy(),
            "session_start_ts": to_ts(all_sessions["day"]).to_numpy(),
        }
    )
    orders = orders.sort_values("day")
    orders_tbl = pd.DataFrame(
        {
            "order_id": np.arange(100_001, 100_001 + len(orders)),
            "user_id": orders["user_id"].to_numpy(),
            "order_ts": to_ts(orders["day"]).to_numpy(),
            "revenue_usd": orders["revenue"].to_numpy(),
            "refunded": orders["refunded"].to_numpy(),
        }
    )

    # ---- write -------------------------------------------------------------------
    data_dir = ROOT / "data"
    data_dir.mkdir(exist_ok=True)
    db_path = data_dir / "experiment.db"
    db_path.unlink(missing_ok=True)
    with sqlite3.connect(db_path) as con:
        con.executescript((ROOT / "sql" / "00_schema.sql").read_text())
        users_tbl.to_sql("users", con, if_exists="append", index=False)
        assign_tbl.to_sql("assignments", con, if_exists="append", index=False)
        sessions_tbl.to_sql("sessions", con, if_exists="append", index=False)
        orders_tbl.to_sql("orders", con, if_exists="append", index=False)
        con.executescript(
            """
            CREATE INDEX idx_sessions_user ON sessions(user_id, session_start_ts);
            CREATE INDEX idx_orders_user   ON orders(user_id, order_ts);
            CREATE INDEX idx_assign_user   ON assignments(user_id);
            """
        )

    # Answer key: NOT read by the analysis, only by scripts/validate.py
    (data_dir / "ground_truth.json").write_text(json.dumps(sim["truth"], indent=2))

    print(f"wrote {db_path.relative_to(ROOT)}")
    for name, df in [("users", users_tbl), ("assignments", assign_tbl), ("sessions", sessions_tbl), ("orders", orders_tbl)]:
        print(f"  {name:<12}{len(df):>10,} rows")


if __name__ == "__main__":
    main()
