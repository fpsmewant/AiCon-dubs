"""CoinBot's independent demo ledger, live observations and round lessons."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

PATH = Path(__file__).with_name("coinbot.sqlite3")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connection():
    db = sqlite3.connect(PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1),
            enabled INTEGER NOT NULL DEFAULT 0, max_window_spend REAL NOT NULL DEFAULT 20,
            take_profit_pct REAL NOT NULL DEFAULT 15, stop_loss_pct REAL NOT NULL DEFAULT 12);
        INSERT OR IGNORE INTO settings(id) VALUES(1);
        CREATE TABLE IF NOT EXISTS snapshots (id INTEGER PRIMARY KEY, ts TEXT NOT NULL,
            ticker TEXT NOT NULL, yes_bid REAL NOT NULL, yes_ask REAL NOT NULL,
            no_bid REAL NOT NULL, no_ask REAL NOT NULL, volume REAL NOT NULL,
            btc_spot REAL);
        CREATE INDEX IF NOT EXISTS idx_coinbot_snapshots ON snapshots(ticker,ts);
        CREATE TABLE IF NOT EXISTS decisions (id INTEGER PRIMARY KEY, ts TEXT NOT NULL,
            ticker TEXT NOT NULL, action TEXT NOT NULL, confidence REAL NOT NULL,
            requested_spend REAL NOT NULL, reason TEXT NOT NULL, executed INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS orders (order_id TEXT PRIMARY KEY, ts TEXT NOT NULL,
            ticker TEXT NOT NULL, outcome TEXT NOT NULL, action TEXT NOT NULL,
            count REAL NOT NULL, yes_price REAL NOT NULL, fee REAL NOT NULL DEFAULT 0);
        CREATE INDEX IF NOT EXISTS idx_coinbot_orders ON orders(ticker,ts);
        CREATE TABLE IF NOT EXISTS equity (id INTEGER PRIMARY KEY, ts TEXT NOT NULL,
            value REAL NOT NULL, ticker TEXT);
        CREATE TABLE IF NOT EXISTS rounds (ticker TEXT PRIMARY KEY, closed_at TEXT NOT NULL,
            result TEXT, pnl REAL NOT NULL, lesson TEXT NOT NULL);
    """)
    try:
        yield db
        db.commit()
    finally:
        db.close()


def settings():
    with connection() as db:
        return dict(db.execute("SELECT * FROM settings WHERE id=1").fetchone())


def update_settings(*, enabled=None, max_window_spend=None, take_profit_pct=None, stop_loss_pct=None):
    values = settings()
    for name, value in locals().copy().items():
        if name in values and value is not None:
            values[name] = value
    with connection() as db:
        db.execute("""UPDATE settings SET enabled=?,max_window_spend=?,take_profit_pct=?,stop_loss_pct=? WHERE id=1""",
                   (int(values["enabled"]), values["max_window_spend"],
                    values["take_profit_pct"], values["stop_loss_pct"]))
    return values


def snapshot(ticker, market, btc_spot=None):
    values = [float(market.get(name) or 0) for name in
              ("yes_bid_dollars", "yes_ask_dollars", "no_bid_dollars", "no_ask_dollars", "volume_fp")]
    with connection() as db:
        db.execute("INSERT INTO snapshots(ts,ticker,yes_bid,yes_ask,no_bid,no_ask,volume,btc_spot) VALUES(?,?,?,?,?,?,?,?)",
                   (now_iso(), ticker, *values, btc_spot))


def recent_snapshots(ticker, limit=24):
    with connection() as db:
        rows = db.execute("SELECT * FROM snapshots WHERE ticker=? ORDER BY id DESC LIMIT ?", (ticker, limit)).fetchall()
    return [dict(row) for row in reversed(rows)]


def record_decision(ticker, action, confidence, requested_spend, reason, executed=False):
    with connection() as db:
        db.execute("INSERT INTO decisions(ts,ticker,action,confidence,requested_spend,reason,executed) VALUES(?,?,?,?,?,?,?)",
                   (now_iso(), ticker, action, confidence, requested_spend, reason, int(executed)))


def record_order(order_id, ticker, outcome, action, count, yes_price, fee=0):
    with connection() as db:
        db.execute("INSERT OR IGNORE INTO orders VALUES(?,?,?,?,?,?,?,?)",
                   (order_id, now_iso(), ticker, outcome, action, count, yes_price, fee))


def orders(ticker=None, limit=50):
    with connection() as db:
        if ticker:
            rows = db.execute("SELECT * FROM orders WHERE ticker=? ORDER BY ts DESC LIMIT ?", (ticker, limit)).fetchall()
        else:
            rows = db.execute("SELECT * FROM orders ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]


def exposure(ticker):
    rows = orders(ticker, 500)
    result = {"yes": {"count": 0.0, "cost": 0.0}, "no": {"count": 0.0, "cost": 0.0}, "spent": 0.0}
    for row in reversed(rows):
        outcome = row["outcome"]
        count = row["count"]
        unit_cost = row["yes_price"] if outcome == "yes" else 1 - row["yes_price"]
        leg = result[outcome]
        if row["action"] == "buy":
            leg["count"] += count
            leg["cost"] += count * unit_cost + row["fee"]
            result["spent"] += count * unit_cost + row["fee"]
        else:
            old_count = leg["count"]
            leg["count"] = max(0, old_count - count)
            leg["cost"] = max(0, leg["cost"] * leg["count"] / old_count) if old_count else 0
    return result


def record_equity(value, ticker):
    with connection() as db:
        db.execute("INSERT INTO equity(ts,value,ticker) VALUES(?,?,?)", (now_iso(), value, ticker))


def equity_today():
    day = datetime.now(timezone.utc).date().isoformat()
    with connection() as db:
        return [dict(row) for row in db.execute("SELECT ts,value,ticker FROM equity WHERE ts>=? ORDER BY id", (day,))]


def round_summary(ticker, result, pnl, lesson):
    with connection() as db:
        db.execute("INSERT OR REPLACE INTO rounds VALUES(?,?,?,?,?)", (ticker, now_iso(), result, pnl, lesson))


def lessons(limit=8):
    with connection() as db:
        return [dict(row) for row in db.execute("SELECT * FROM rounds ORDER BY closed_at DESC LIMIT ?", (limit,))]


def unscored_tickers(limit=5):
    with connection() as db:
        return [row["ticker"] for row in db.execute("""SELECT DISTINCT o.ticker FROM orders o
            LEFT JOIN rounds r ON r.ticker=o.ticker WHERE r.ticker IS NULL
            ORDER BY o.ts DESC LIMIT ?""", (limit,))]
