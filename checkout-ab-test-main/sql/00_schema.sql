-- Raw event tables, as they'd land from the tracking pipeline.

CREATE TABLE users (
    user_id     INTEGER PRIMARY KEY,
    signup_ts   TEXT    NOT NULL,
    platform    TEXT    NOT NULL,           -- 'mobile' | 'desktop'
    country     TEXT    NOT NULL,
    is_bot      INTEGER NOT NULL DEFAULT 0  -- flagged by the bot-detection job
);

-- One row per assignment *event*. Not unique per user: duplicates and a
-- known logging bug mean some users appear more than once.
CREATE TABLE assignments (
    user_id       INTEGER NOT NULL,
    experiment_id TEXT    NOT NULL,
    variant       TEXT    NOT NULL,         -- 'control' | 'treatment'
    assigned_ts   TEXT    NOT NULL
);

CREATE TABLE sessions (
    session_id        INTEGER PRIMARY KEY,
    user_id           INTEGER NOT NULL,
    session_start_ts  TEXT    NOT NULL
);

CREATE TABLE orders (
    order_id     INTEGER PRIMARY KEY,
    user_id      INTEGER NOT NULL,
    order_ts     TEXT    NOT NULL,
    revenue_usd  REAL    NOT NULL,
    refunded     INTEGER NOT NULL DEFAULT 0
);
