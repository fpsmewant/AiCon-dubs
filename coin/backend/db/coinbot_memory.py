"""Independent SQLite journal for CoinBot's US stock paper trades."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

PATH = Path(__file__).with_name("stockbot.sqlite3")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connection():
    db = sqlite3.connect(PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK(id=1), enabled INTEGER NOT NULL DEFAULT 0,
            max_trade_budget REAL NOT NULL DEFAULT 1000,
            take_profit_pct REAL NOT NULL DEFAULT 3,
            stop_loss_pct REAL NOT NULL DEFAULT 1.5
        );
        INSERT OR IGNORE INTO settings(id) VALUES(1);
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY, ts TEXT NOT NULL, symbol TEXT NOT NULL,
            price REAL NOT NULL, volume REAL NOT NULL DEFAULT 0,
            change_pct REAL, source_time TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_stockbot_snapshots ON snapshots(symbol, ts);
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY, ts TEXT NOT NULL, symbol TEXT NOT NULL,
            action TEXT NOT NULL, confidence REAL NOT NULL,
            budget REAL NOT NULL, reason TEXT NOT NULL, submitted INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS trades (
            order_id TEXT PRIMARY KEY, ts TEXT NOT NULL, symbol TEXT NOT NULL,
            qty INTEGER NOT NULL, estimated_entry REAL NOT NULL,
            stop_price REAL NOT NULL, target_price REAL NOT NULL,
            status TEXT NOT NULL, filled_qty REAL NOT NULL DEFAULT 0,
            entry_price REAL, exit_price REAL, exit_time TEXT, pnl REAL,
            lesson TEXT, close_order_id TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_stockbot_trades ON trades(ts);
        CREATE TABLE IF NOT EXISTS performance (
            id INTEGER PRIMARY KEY, ts TEXT NOT NULL, pnl REAL NOT NULL
        );
    """)
    try:
        yield db
        db.commit()
    finally:
        db.close()


def settings():
    with connection() as db:
        return dict(db.execute("SELECT * FROM settings WHERE id=1").fetchone())


def update_settings(**changes):
    allowed = {"enabled", "max_trade_budget", "take_profit_pct", "stop_loss_pct"}
    if set(changes) - allowed:
        raise ValueError("Invalid CoinBot setting")
    values = settings() | changes
    with connection() as db:
        db.execute("""UPDATE settings SET enabled=?, max_trade_budget=?,
            take_profit_pct=?, stop_loss_pct=? WHERE id=1""",
            (int(values["enabled"]), values["max_trade_budget"],
             values["take_profit_pct"], values["stop_loss_pct"]))
    return values


def snapshot(symbol, price, volume=0, change_pct=None, source_time=None):
    with connection() as db:
        db.execute("""INSERT INTO snapshots(ts,symbol,price,volume,change_pct,source_time)
            VALUES(?,?,?,?,?,?)""",
            (now_iso(), symbol, price, volume, change_pct, source_time))


def recent_snapshots(symbol, limit=90):
    with connection() as db:
        rows = db.execute("SELECT * FROM snapshots WHERE symbol=? ORDER BY id DESC LIMIT ?",
                          (symbol, limit)).fetchall()
    return [dict(row) for row in reversed(rows)]


def decision(symbol, action, confidence, budget, reason, submitted=False):
    with connection() as db:
        db.execute("""INSERT INTO decisions(ts,symbol,action,confidence,budget,reason,submitted)
            VALUES(?,?,?,?,?,?,?)""", (now_iso(), symbol, action, confidence,
                                      budget, reason, int(submitted)))


def last_decision():
    with connection() as db:
        row = db.execute("SELECT * FROM decisions ORDER BY id DESC LIMIT 1").fetchone()
    return dict(row) if row else None


def record_trade(order_id, symbol, qty, entry, stop, target, status):
    with connection() as db:
        db.execute("""INSERT INTO trades(order_id,ts,symbol,qty,estimated_entry,
            stop_price,target_price,status) VALUES(?,?,?,?,?,?,?,?)""",
            (order_id, now_iso(), symbol, qty, entry, stop, target, status))


def update_trade(order_id, **changes):
    allowed = {"status", "filled_qty", "entry_price", "exit_price", "exit_time", "pnl", "lesson", "close_order_id"}
    if not changes or set(changes) - allowed:
        raise ValueError("Invalid trade update")
    with connection() as db:
        db.execute("UPDATE trades SET " + ",".join(f"{key}=?" for key in changes) +
                   " WHERE order_id=?", (*changes.values(), order_id))


def trades(limit=30):
    with connection() as db:
        return [dict(row) for row in db.execute(
            "SELECT * FROM trades ORDER BY ts DESC LIMIT ?", (limit,))]


def open_trades():
    with connection() as db:
        return [dict(row) for row in db.execute(
            "SELECT * FROM trades WHERE status NOT IN ('closed','canceled','expired','rejected') ORDER BY ts DESC")]


def lessons(symbol=None, limit=8):
    with connection() as db:
        if symbol:
            rows = db.execute("""SELECT symbol,pnl,lesson,exit_time FROM trades
                WHERE status='closed' AND symbol=? ORDER BY exit_time DESC LIMIT ?""",
                (symbol, limit)).fetchall()
        else:
            rows = db.execute("""SELECT symbol,pnl,lesson,exit_time FROM trades
                WHERE status='closed' ORDER BY exit_time DESC LIMIT ?""", (limit,)).fetchall()
    return [dict(row) for row in rows]


def realized_today():
    day = datetime.now(timezone.utc).date().isoformat()
    with connection() as db:
        return float(db.execute("""SELECT COALESCE(SUM(pnl),0) FROM trades
            WHERE status='closed' AND exit_time>=?""", (day,)).fetchone()[0])


def record_performance(marks):
    total = realized_today()
    for trade in open_trades():
        if trade["filled_qty"] and trade["entry_price"] and trade["symbol"] in marks:
            total += trade["filled_qty"] * (marks[trade["symbol"]] - trade["entry_price"])
    with connection() as db:
        db.execute("INSERT INTO performance(ts,pnl) VALUES(?,?)", (now_iso(), round(total, 2)))
    return round(total, 2)


def performance_today():
    day = datetime.now(timezone.utc).date().isoformat()
    with connection() as db:
        return [dict(row) for row in db.execute(
            "SELECT ts,pnl FROM performance WHERE ts>=? ORDER BY id", (day,))]
