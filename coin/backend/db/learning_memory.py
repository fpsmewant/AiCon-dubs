"""Durable trade observations and comparable outcome lookup."""

import json
import math
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

PATH = Path(__file__).with_name("memory.sqlite3")


@contextmanager
def connection():
    db = sqlite3.connect(PATH, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS trades (
        order_id TEXT PRIMARY KEY, symbol TEXT NOT NULL, side TEXT NOT NULL,
        submitted_at TEXT NOT NULL, entry REAL NOT NULL, stop REAL NOT NULL,
        target REAL NOT NULL, qty REAL NOT NULL, pre_snapshot TEXT NOT NULL,
        post_snapshot TEXT, exit_snapshot TEXT, outcome TEXT, return_pct REAL
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol_outcome ON trades(symbol,outcome)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_trades_due ON trades(submitted_at,post_snapshot)")
    columns = {row['name'] for row in db.execute('PRAGMA table_info(trades)')}
    if 'status' not in columns:
        db.execute("ALTER TABLE trades ADD COLUMN status TEXT NOT NULL DEFAULT 'filled'")
    try:
        yield db
        db.commit()
    finally:
        db.close()


def record_trade(order_id: str, proposal, pre_snapshot: dict, submitted_at: datetime | None = None,
                 status: str = 'filled') -> None:
    submitted_at = submitted_at or datetime.now(timezone.utc)
    with connection() as db:
        db.execute("""INSERT OR IGNORE INTO trades
            (order_id,symbol,side,submitted_at,entry,stop,target,qty,pre_snapshot,status)
            VALUES(?,?,?,?,?,?,?,?,?,?)""", (order_id, proposal.symbol, proposal.side.value,
            submitted_at.isoformat(), proposal.target_entry_price, proposal.stop_loss_price,
            proposal.take_profit_price, proposal.qty, json.dumps(pre_snapshot), status))


def score_trade(order_id: str, post_snapshot: dict | None, exit_snapshot: dict | None = None) -> dict:
    with connection() as db:
        row = db.execute("SELECT * FROM trades WHERE order_id=?", (order_id,)).fetchone()
        if row is None:
            raise KeyError(order_id)
        existing_exit = json.loads(row['exit_snapshot']) if row['exit_snapshot'] else None
        price = float((exit_snapshot or existing_exit or post_snapshot)["price"])
        direction = 1 if row["side"] == "buy" else -1
        return_pct = direction * (price / row["entry"] - 1) * 100
        outcome = "GOOD" if return_pct > 0 else "BAD"
        db.execute("""UPDATE trades SET post_snapshot=COALESCE(?,post_snapshot),exit_snapshot=COALESCE(?,exit_snapshot),
            outcome=?,return_pct=? WHERE order_id=?""",
            (json.dumps(post_snapshot) if post_snapshot else None, json.dumps(exit_snapshot) if exit_snapshot else None,
             outcome, return_pct, order_id))
    return {"outcome": outcome, "return_pct": round(return_pct, 3)}


def due_trades(now: datetime | None = None) -> list[dict]:
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(minutes=30)
    with connection() as db:
        rows = db.execute("SELECT * FROM trades WHERE status='filled' AND post_snapshot IS NULL AND submitted_at<=?",
                          (cutoff.isoformat(),)).fetchall()
    return [dict(row) for row in rows]


def open_trades() -> list[dict]:
    with connection() as db:
        return [dict(row) for row in db.execute("SELECT * FROM trades WHERE status IN ('pending','filled') AND exit_snapshot IS NULL")]


def update_fill(order_id: str, price: float, qty: float, filled_at: datetime, pre: dict) -> None:
    with connection() as db:
        db.execute("UPDATE trades SET entry=?,qty=?,submitted_at=?,pre_snapshot=?,status='filled' WHERE order_id=?",
                   (price, qty, filled_at.isoformat(), json.dumps(pre), order_id))


def cancel_pending(order_id: str) -> None:
    with connection() as db:
        db.execute("UPDATE trades SET status='canceled' WHERE order_id=? AND status='pending'", (order_id,))


def similar_losses(symbol: str, snapshot: dict, limit: int = 3) -> list[dict]:
    with connection() as db:
        rows = db.execute("SELECT * FROM trades WHERE symbol=? AND outcome='BAD' ORDER BY submitted_at DESC LIMIT 100",
                          (symbol.upper(),)).fetchall()
    scored = []
    for row in rows:
        previous = json.loads(row["pre_snapshot"])
        # Scale-independent signals; price alone should not imply similar conditions.
        keys = ("volatility", "sentiment_score", "volume")
        available = [(float(snapshot[k]), float(previous[k])) for k in keys
                     if snapshot.get(k) is not None and previous.get(k) is not None]
        if len(available) < 2:
            continue
        distance = math.sqrt(sum(((a - b) / max(abs(a), abs(b), 1)) ** 2 for a, b in available) / len(available))
        if distance <= 0.35:
            scored.append({"order_id": row["order_id"], "return_pct": row["return_pct"],
                           "distance": round(distance, 3), "snapshot": previous})
    return sorted(scored, key=lambda item: item["distance"])[:limit]
