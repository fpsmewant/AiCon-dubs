"""Opt-in US stock paper trader with broker-hosted profit and loss exits."""

import json
import math
import os
import threading
import time
from datetime import datetime, timezone

from db import coinbot_memory as memory
from db.mandates import load_mandate
from execution.alpaca_client import AlpacaClient
from intelligence.agents import gemini_client
from intelligence.data_feeds.market_data import market_summary, minute_history
from intelligence.data_feeds.marketaux import cached_news, sync_news

SYMBOLS = ("AAPL", "NVDA", "TSLA", "MSFT", "AMD")
NAMES = {"AAPL": "Apple", "NVDA": "Nvidia", "TSLA": "Tesla",
         "MSFT": "Microsoft", "AMD": "AMD"}
POLL_SECONDS = 15
DECISION_SECONDS = 60
_lock = threading.RLock()
_runtime = {"phase": "paused", "error": None, "quotes": [], "selected": "NVDA",
            "chart": [], "chart_at": 0.0, "last_decision_at": 0.0,
            "news_at": 0.0, "news_symbol": None, "news": [], "last_performance_at": 0.0,
            "next_open": None, "last_tick": None, "market_open": False}


def _fresh(quote, now):
    try:
        timestamp = datetime.fromisoformat(quote["as_of"].replace("Z", "+00:00"))
        return (now - timestamp).total_seconds() <= 90 and float(quote["price"]) > 0
    except (KeyError, TypeError, ValueError):
        return False


def _rank(quotes):
    """Prefer a meaningful recent move; never manufacture a signal from daily change."""
    ranked = []
    for quote in quotes:
        symbol = quote["symbol"]
        if symbol not in SYMBOLS or not quote.get("price"):
            continue
        cutoff = datetime.now(timezone.utc).timestamp() - 600
        samples = [row for row in memory.recent_snapshots(symbol, 24)
                   if datetime.fromisoformat(row["ts"]).timestamp() >= cutoff]
        if len(samples) < 5:
            continue
        age = (datetime.fromisoformat(samples[-1]["ts"]) -
               datetime.fromisoformat(samples[0]["ts"])).total_seconds()
        if age < 60 or samples[0]["price"] <= 0:
            continue
        move = 100 * (samples[-1]["price"] / samples[0]["price"] - 1)
        ranked.append((abs(move), move, quote))
    return sorted(ranked, key=lambda row: row[0], reverse=True)


def _news(symbol):
    if _runtime["news_symbol"] != symbol or time.monotonic() - _runtime["news_at"] > 300:
        try:
            result = sync_news(countries="us", symbols=symbol, limit=5)
            _runtime["news"] = result.get("articles", [])[:5]
        except Exception:
            try:
                _runtime["news"] = cached_news(symbols=symbol, limit=5).get("articles", [])
            except Exception:
                _runtime["news"] = []
        _runtime["news_at"] = time.monotonic()
        _runtime["news_symbol"] = symbol
    return [{"title": row.get("title"), "published_at": row.get("published_at"),
             "sentiment": row.get("sentiment_score")} for row in _runtime["news"][:5]]


def _decide(symbol, move, quote, config, budget):
    lessons = memory.lessons(symbol, 6)
    recent_losses = sum(1 for row in lessons[:3] if row["pnl"] is not None and row["pnl"] < 0)
    if move < 0.25:
        return {"action": "WAIT", "confidence": 0, "budget": 0,
                "reason": "Waiting for a clearer upward move."}
    if recent_losses >= 2:
        return {"action": "WAIT", "confidence": 0, "budget": 0,
                "reason": "Similar recent trades lost money; waiting for new conditions."}
    prompt = (
        "You are CoinBot, an opt-in US stock paper day trader. Only long BUY or WAIT. "
        "Return JSON only: action, confidence 0..1, budget in USD, reason under 160 chars. "
        "Use only supplied observations. Require a credible intraday edge beyond spread/slippage; "
        "when uncertain, choose WAIT. Past outcomes are lessons, not predictions. "
        f"Symbol {symbol}; current IEX trade {quote['price']}; recent move {move:+.3f}%; "
        f"previous close change {quote.get('change_pct')}; "
        f"live observations {json.dumps(memory.recent_snapshots(symbol, 12))}; "
        f"recent headlines {json.dumps(_news(symbol))}; "
        f"past trade lessons {json.dumps(lessons)}; "
        f"maximum spend {budget:.2f}; profit target {config['take_profit_pct']}%; "
        f"loss stop {config['stop_loss_pct']}%."
    )
    try:
        answer = json.loads(gemini_client.complete(prompt, json_mode=True, prefer_tertiary=True))
        return {"action": "BUY" if str(answer.get("action", "WAIT")).upper() == "BUY" else "WAIT",
                "confidence": max(0, min(1, float(answer.get("confidence") or 0))),
                "budget": max(0, min(budget, float(answer.get("budget") or 0))),
                "reason": str(answer.get("reason") or "No clear edge.")[:160]}
    except Exception:
        return {"action": "WAIT", "confidence": 0, "budget": 0,
                "reason": "Analysis unavailable; waiting for the next check."}


def _reconcile(client):
    for trade in memory.open_trades():
        order = client.get_order(trade["order_id"])
        filled = float(order.get("filled_qty") or 0)
        changes = {"status": order["status"], "filled_qty": filled}
        if order.get("filled_avg_price"):
            changes["entry_price"] = order["filled_avg_price"]
        if trade.get("close_order_id"):
            exit_order = client.get_order(trade["close_order_id"])
            if exit_order["status"] == "filled":
                changes.update(_closed(trade, filled, order, exit_order))
            else:
                changes["status"] = "closing"
        else:
            exit_leg = next((leg for leg in order.get("legs", []) if leg["status"] == "filled"), None)
            if exit_leg:
                changes.update(_closed(trade, filled, order, exit_leg))
        if changes["status"] in ("canceled", "expired", "rejected") and filled > 0:
            changes["status"] = "filled"  # A partial fill still represents exposure.
        memory.update_trade(trade["order_id"], **changes)


def _closed(trade, filled, entry_order, exit_order):
    entry = entry_order.get("filled_avg_price") or trade["entry_price"]
    exit_price = exit_order.get("filled_avg_price")
    if not entry or not exit_price:
        return {"status": "closing"}
    pnl = round(filled * (exit_price - entry), 2)
    return {"status": "closed", "exit_price": exit_price,
            "exit_time": exit_order.get("filled_at") or memory.now_iso(),
            "pnl": pnl,
            "lesson": f"{trade['symbol']} {'gain' if pnl >= 0 else 'loss'} of ${abs(pnl):.2f}; "
                      f"entry ${entry:.2f}, exit ${exit_price:.2f}."}


def _budget(config, mandate, account, price):
    if mandate is None:
        return 0, "Save a risk mandate before starting coinBot."
    if account["daily_loss"] >= mandate.max_daily_loss:
        return 0, "Daily loss limit reached."
    if memory.realized_today() <= -mandate.max_daily_loss:
        return 0, "CoinBot daily loss limit reached."
    budget = min(config["max_trade_budget"], mandate.max_position_size,
                 mandate.allocated_capital, account["buying_power"] * 0.95,
                 mandate.max_loss_per_trade * 100 / config["stop_loss_pct"])
    if budget < price * 1.02:
        return 0, "Budget is below the price of one share with a safety reserve."
    return budget, None


def tick(client=None, now=None):
    """One market check; all order guards are repeated immediately before submission."""
    now = now or datetime.now(timezone.utc)
    config = memory.settings()
    summary = market_summary()
    quotes = [quote for quote in summary["quotes"] if quote["symbol"] in SYMBOLS]
    _runtime.update(quotes=quotes, next_open=summary.get("next_open"),
                    last_tick=summary.get("fetched_at"), market_open=summary["is_open"])
    selected = _runtime["selected"]
    if summary["is_open"]:
        for quote in quotes:
            if _fresh(quote, now):
                memory.snapshot(quote["symbol"], quote["price"],
                                volume=quote.get("volume") or 0,
                                change_pct=quote.get("change_pct"), source_time=quote["as_of"])
    if time.monotonic() - _runtime["chart_at"] > 300:
        try:
            _runtime["chart"] = minute_history(selected)
            _runtime["chart_at"] = time.monotonic()
        except Exception:
            pass
    if config["enabled"] or memory.open_trades():
        client = client or AlpacaClient()
        _reconcile(client)
    marks = {row["symbol"]: row["price"] for row in quotes if row.get("price")}
    if (config["enabled"] or memory.open_trades()) and time.monotonic() - _runtime["last_performance_at"] > 30:
        memory.record_performance(marks)
        _runtime["last_performance_at"] = time.monotonic()
    if not config["enabled"]:
        _runtime["phase"] = "paused"
        return
    if not summary["is_open"]:
        _runtime["phase"] = "market_closed"
        return
    if memory.open_trades():
        _runtime["phase"] = "managing_position"
        return
    if time.monotonic() - _runtime["last_decision_at"] < DECISION_SECONDS:
        _runtime["phase"] = "scanning"
        return
    blocked_symbols = {position["symbol"] for position in client.get_positions()}
    blocked_symbols.update(client.get_open_order_symbols())
    ranked = [row for row in _rank(quotes) if row[2]["symbol"] not in blocked_symbols]
    if not ranked:
        _runtime["phase"] = "observing"
        return
    _, move, quote = ranked[0]
    symbol = quote["symbol"]
    _runtime["selected"] = symbol
    if not _fresh(quote, now):
        _runtime["phase"] = "stale_data"
        return
    account = client.get_account()
    mandate = load_mandate()
    budget, block = _budget(config, mandate, account, quote["price"])
    if block:
        memory.decision(symbol, "WAIT", 0, 0, block)
        _runtime["phase"] = "risk_limit"
        return
    _runtime["phase"] = "thinking"
    _runtime["last_decision_at"] = time.monotonic()
    decision = _decide(symbol, move, quote, config, budget)
    submitted = False
    if decision["action"] == "BUY" and decision["confidence"] >= 0.75:
        with _lock:
            if (memory.settings()["enabled"] and not memory.open_trades() and
                    market_summary()["is_open"] and _fresh(quote, datetime.now(timezone.utc)) and
                    not any(p["symbol"] == symbol for p in client.get_positions()) and
                    symbol not in client.get_open_order_symbols()):
                account = client.get_account()
                budget, block = _budget(config, load_mandate(), account, quote["price"])
                spend = min(decision["budget"], budget)
                qty = math.floor(spend / (quote["price"] * 1.02)) if not block else 0
                if qty >= 1:
                    stop = round(quote["price"] * (1 - config["stop_loss_pct"] / 100), 2)
                    target = round(quote["price"] * (1 + config["take_profit_pct"] / 100), 2)
                    order = client.place_stock_bracket(symbol, qty, stop, target)
                    memory.record_trade(order["id"], symbol, qty, quote["price"],
                                        stop, target, order["status"])
                    submitted = True
    memory.decision(symbol, decision["action"], decision["confidence"],
                    decision["budget"], decision["reason"], submitted)
    _runtime["phase"] = "managing_position" if submitted else "scanning"


def run(stop_event):
    while not stop_event.is_set():
        try:
            tick()
            _runtime["error"] = None
        except Exception as exc:
            _runtime["error"] = str(exc)[:180]
        stop_event.wait(POLL_SECONDS)


def start(config):
    client = AlpacaClient()
    client.get_account()  # Authenticate the paper account before enabling orders.
    if load_mandate() is None:
        raise ValueError("Save the trading risk settings before starting coinBot.")
    with _lock:
        memory.update_settings(enabled=True, max_trade_budget=config.max_trade_budget,
            take_profit_pct=config.take_profit_pct, stop_loss_pct=config.stop_loss_pct)
        _runtime["error"] = None
    return status()


def stop():
    with _lock:
        memory.update_settings(enabled=False)
        _runtime["phase"] = "paused"
    return status()


def select_symbol(symbol):
    if symbol not in SYMBOLS:
        raise ValueError("Choose a stock from the CoinBot watchlist.")
    _runtime["selected"] = symbol
    _runtime["chart_at"] = 0.0
    _runtime["chart"] = []
    return status()


def close_position():
    with _lock:
        open_items = [row for row in memory.open_trades() if row["filled_qty"] > 0]
        if not open_items:
            raise ValueError("CoinBot has no filled position to close.")
        trade = open_items[0]
        client = AlpacaClient()
        order = client.get_order(trade["order_id"])
        if any(leg["status"] == "filled" for leg in order.get("legs", [])):
            _reconcile(client)
            raise ValueError("The position was already closed by its profit target or safety stop.")
        positions = {row["symbol"]: row for row in client.get_positions()}
        held = positions.get(trade["symbol"], {}).get("qty", 0)
        qty = min(math.floor(trade["filled_qty"]), math.floor(held))
        if qty < 1:
            raise ValueError("No bot shares remain in the account.")
        legs = [leg["id"] for leg in order.get("legs", []) if leg["status"] in
                ("new", "accepted", "held", "pending_new")]
        closing = client.close_bot_position(trade["symbol"], qty, legs)
        memory.update_trade(trade["order_id"], status="closing", close_order_id=closing["id"])
        return closing


def status():
    config = memory.settings()
    selected = _runtime["selected"]
    live = memory.recent_snapshots(selected, 90)
    chart = live if len(live) >= 5 else _runtime["chart"]
    return {"enabled": bool(config["enabled"]),
            "configured": bool(os.getenv("ALPACA_API_KEY") and os.getenv("ALPACA_SECRET_KEY")),
            "config": {key: config[key] for key in
                       ("max_trade_budget", "take_profit_pct", "stop_loss_pct")},
            "phase": _runtime["phase"], "error": _runtime["error"],
            "symbols": SYMBOLS, "names": NAMES, "selected": selected,
            "quotes": _runtime["quotes"], "chart": chart,
            "next_open": _runtime["next_open"], "last_tick": _runtime["last_tick"],
            "market_open": _runtime["market_open"],
            "decision": memory.last_decision(), "orders": memory.trades(),
            "positions": memory.open_trades(), "performance": memory.performance_today(),
            "lessons": memory.lessons()}
