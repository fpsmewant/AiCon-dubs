"""Continuous, opt-in demo trader for 15-minute BTC event markets."""

import json
import math
import os
import threading
import time
from datetime import datetime, timedelta, timezone

import requests

from db import coinbot_memory as memory
from execution.kalshi_demo import CoinBotDemoClient
from intelligence.agents import gemini_client


SERIES = "KXBTC15M"
OBSERVATION_SECONDS = 120
POLL_SECONDS = 5
DECISION_SECONDS = 35
_lock = threading.RLock()
_runtime = {"phase": "idle", "market": None, "error": None, "last_decision": None,
            "last_decision_at": 0.0, "last_equity_at": 0.0, "last_discovery_at": 0.0,
            "current_ticker": None, "upcoming": None, "client": None,
            "last_settlement_at": 0.0}


def _parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def market_phase(market, now=None):
    now = now or datetime.now(timezone.utc)
    opened, closes = _parse_time(market["open_time"]), _parse_time(market["close_time"])
    if not opened <= now < closes:
        return "outside"
    if (now - opened).total_seconds() < OBSERVATION_SECONDS:
        return "observing"
    return "trading"


def _select_market(markets, now=None):
    now = now or datetime.now(timezone.utc)
    valid = [market for market in markets if market.get("ticker", "").startswith(SERIES + "-")
             and market.get("open_time") and market.get("close_time")
             and 800 <= (_parse_time(market["close_time"]) - _parse_time(market["open_time"])).total_seconds() <= 1200]
    active = sorted((m for m in valid if _parse_time(m["open_time"]) <= now < _parse_time(m["close_time"])),
                    key=lambda m: m["close_time"])
    upcoming = sorted((m for m in valid if _parse_time(m["open_time"]) > now), key=lambda m: m["open_time"])
    return (active[0] if active else None), (upcoming[0] if upcoming else None)


def _spot():
    try:
        response = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot", timeout=(3, 5))
        response.raise_for_status()
        return float(response.json()["data"]["amount"])
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return None


def _quotes(market):
    return {key: float(market.get(key) or 0) for key in
            ("yes_bid_dollars", "yes_ask_dollars", "no_bid_dollars", "no_ask_dollars")}


def _order(client, market, outcome, action, count):
    quotes = _quotes(market)
    yes_price = quotes["yes_ask_dollars"] if (outcome == "yes") == (action == "buy") else quotes["yes_bid_dollars"]
    if not 0.01 <= yes_price <= 0.99:
        raise ValueError("There is no executable quote for that trade")
    response = client.order(ticker=market["ticker"], outcome=outcome, action=action,
                            count=count, yes_price=yes_price)
    filled = float(response.get("fill_count") or 0)
    if filled > 0:
        memory.record_order(response["order_id"], market["ticker"], outcome, action,
                            filled, float(response.get("average_fill_price") or yes_price),
                            filled * float(response.get("average_fee_paid") or 0))
    return {"order_id": response.get("order_id"), "filled": filled, "requested": count,
            "outcome": outcome, "action": action, "yes_price": yes_price}


def _auto_exit(client, market, config):
    exposure = memory.exposure(market["ticker"])
    quotes = _quotes(market)
    for outcome in ("yes", "no"):
        leg = exposure[outcome]
        if leg["count"] < 1 or leg["cost"] <= 0:
            continue
        exit_price = quotes[f"{outcome}_bid_dollars"]
        if exit_price <= 0:
            continue
        return_pct = 100 * (exit_price * leg["count"] / leg["cost"] - 1)
        if return_pct >= config["take_profit_pct"] or return_pct <= -config["stop_loss_pct"]:
            result = _order(client, market, outcome, "sell", math.floor(leg["count"]))
            memory.record_decision(market["ticker"], "CLOSE", 1, 0,
                f"User profit/loss threshold reached ({return_pct:+.1f}%).", result["filled"] > 0)
            _runtime["last_decision"] = {"action": "CLOSE", "reason": "Profit/loss threshold reached.",
                                         "confidence": 1, "order": result}
            return True
    return False


def _decide(market, config):
    ticker = market["ticker"]
    snapshots = memory.recent_snapshots(ticker, 20)
    if len(snapshots) < 6:
        return {"action": "WAIT", "confidence": 0, "dollars": 0,
                "reason": "Collecting live market samples."}
    quotes = _quotes(market)
    if any(not 0 < quotes[key] < 1 for key in ("yes_bid_dollars", "yes_ask_dollars",
                                               "no_bid_dollars", "no_ask_dollars")):
        return {"action": "WAIT", "confidence": 0, "dollars": 0,
                "reason": "Waiting for complete, executable quotes."}
    if quotes["yes_ask_dollars"] - quotes["yes_bid_dollars"] > .12:
        return {"action": "WAIT", "confidence": 0, "dollars": 0,
                "reason": "Market spread is too wide for a clear entry."}
    exposure = memory.exposure(ticker)
    remaining = max(0, config["max_window_spend"] - exposure["spent"])
    lessons = [row for row in memory.lessons() if row["result"] in ("yes", "no")]
    prompt = ("You are CoinBot, a cautious demo-only trader in one 15-minute BTC up/down market. "
        "Return JSON only with action BUY_YES, BUY_NO, CLOSE, or WAIT; confidence 0..1; dollars 0..remaining_budget; reason under 160 characters. "
        "Require a plausible edge after spread and fees. A market price is not an independent forecast. "
        "If evidence is thin, inconsistent, or the remaining time is too short, WAIT. "
        "Past results are lessons, not proof of future returns. Never invent data.\n"
        f"Market: {ticker}; closes {market['close_time']}; current UTC {datetime.now(timezone.utc).isoformat()}\n"
        f"Quotes: {json.dumps(quotes)}; volume: {market.get('volume_fp')}\n"
        f"Last live observations (BTC spot is an indicator, not the settlement index): {json.dumps(snapshots[-12:])}\n"
        f"Own open exposure: {json.dumps(exposure)}; remaining spend: {remaining:.2f}; "
        f"profit target {config['take_profit_pct']}%; loss threshold {config['stop_loss_pct']}%.\n"
        f"Past completed rounds: {json.dumps(lessons[:6])}")
    try:
        parsed = json.loads(gemini_client.complete(prompt, json_mode=True, prefer_tertiary=True))
        action = str(parsed.get("action", "WAIT")).upper()
        if action not in {"BUY_YES", "BUY_NO", "CLOSE", "WAIT"}:
            action = "WAIT"
        return {"action": action, "confidence": max(0, min(1, float(parsed.get("confidence") or 0))),
                "dollars": max(0, min(remaining, float(parsed.get("dollars") or 0))),
                "reason": str(parsed.get("reason") or "No clear edge.")[:160]}
    except (ValueError, TypeError, KeyError, RuntimeError, requests.RequestException):
        return {"action": "WAIT", "confidence": 0, "dollars": 0,
                "reason": "Decision service unavailable; waiting for the next check."}


def _act(client, market, config, decision):
    ticker = market["ticker"]
    action = decision["action"]
    exposure = memory.exposure(ticker)
    executed = False
    if action.startswith("BUY_") and decision["confidence"] >= .70:
        outcome = action.split("_")[1].lower()
        opposite = "no" if outcome == "yes" else "yes"
        quotes = _quotes(market)
        price = quotes[f"{outcome}_ask_dollars"]
        remaining = max(0, config["max_window_spend"] - exposure["spent"])
        budget = min(decision["dollars"], remaining)
        count = math.floor(budget / (price + .04)) if price > 0 else 0
        if count >= 1 and exposure[opposite]["count"] == 0:
            cash = float(client.balance().get("balance") or 0) / 100
            if budget <= cash and market_phase(market) == "trading":
                result = _order(client, market, outcome, "buy", count)
                decision["order"] = result
                executed = result["filled"] > 0
    elif action == "CLOSE" and decision["confidence"] >= .70:
        for outcome in ("yes", "no"):
            if exposure[outcome]["count"] >= 1 and market_phase(market) == "trading":
                result = _order(client, market, outcome, "sell", math.floor(exposure[outcome]["count"]))
                decision["order"] = result
                executed = result["filled"] > 0
                break
    memory.record_decision(ticker, action, decision["confidence"], decision["dollars"],
                           decision["reason"], executed)
    _runtime["last_decision"] = decision


def _finalize_round(client, ticker):
    if not ticker or any(row["ticker"] == ticker for row in memory.lessons(100)):
        return
    rows = memory.orders(ticker, 500)
    if not rows:
        return
    market = client.market(ticker)
    result = str(market.get("result") or "").lower()
    if result not in ("yes", "no"):
        return
    pnl = 0.0
    for row in rows:
        unit = row["yes_price"] if row["outcome"] == "yes" else 1 - row["yes_price"]
        pnl += (1 if row["action"] == "sell" else -1) * row["count"] * unit - row["fee"]
    exposure = memory.exposure(ticker)
    pnl += exposure[result]["count"]
    lesson = ("Positive realized outcome" if pnl > 0 else "Loss after spread, fees and settlement")
    memory.round_summary(ticker, result, round(pnl, 2), lesson)


def tick(client=None, now=None):
    """One observed round step. Exposed for deterministic tests and the background loop."""
    with _lock:
        client = client or _runtime["client"] or CoinBotDemoClient()
        now = now or datetime.now(timezone.utc)
        if time.monotonic() - _runtime["last_discovery_at"] > 5 or not _runtime["market"]:
            current, upcoming = _select_market(client.markets(), now)
            if not current:
                _, upcoming = _select_market(client.markets("unopened"), now)
            _runtime["market"] = current
            _runtime["upcoming"] = upcoming
            _runtime["last_discovery_at"] = time.monotonic()
        market = _runtime["market"]
        if time.monotonic() - _runtime["last_settlement_at"] >= 30:
            for old_ticker in memory.unscored_tickers(3):
                if not market or old_ticker != market["ticker"]:
                    _finalize_round(client, old_ticker)
            _runtime["last_settlement_at"] = time.monotonic()
        if not market:
            _runtime["phase"] = "waiting"
            return
        ticker = market["ticker"]
        if _runtime["current_ticker"] and _runtime["current_ticker"] != ticker:
            _finalize_round(client, _runtime["current_ticker"])
            _runtime["last_decision_at"] = 0
            _runtime["last_decision"] = None
        _runtime["current_ticker"] = ticker
        market = client.market(ticker)
        _runtime["market"] = market
        phase = market_phase(market, now)
        _runtime["phase"] = phase
        if phase == "outside":
            _runtime["last_discovery_at"] = 0
            return
        spot = _spot()
        memory.snapshot(ticker, market, spot)
        config = memory.settings()
        if time.monotonic() - _runtime["last_equity_at"] >= 30:
            balance = client.balance()
            memory.record_equity((float(balance.get("balance") or 0) +
                                  float(balance.get("portfolio_value") or 0)) / 100, ticker)
            _runtime["last_equity_at"] = time.monotonic()
        if not config["enabled"] or phase != "trading":
            return
        if _auto_exit(client, market, config):
            _runtime["last_decision_at"] = time.monotonic()
            return
        if time.monotonic() - _runtime["last_decision_at"] < DECISION_SECONDS:
            return
        _runtime["last_decision_at"] = time.monotonic()
        decision = _decide(market, config)
        _act(client, market, config, decision)


def run(stop_event):
    while not stop_event.is_set():
        try:
            tick()
            _runtime["error"] = None
        except Exception as exc:
            _runtime["error"] = str(exc)[:180]
        stop_event.wait(POLL_SECONDS)


def start(config):
    client = CoinBotDemoClient()
    client.balance()  # Prove demo authentication before arming automatic orders.
    with _lock:
        memory.update_settings(enabled=True, max_window_spend=config.max_window_spend,
            take_profit_pct=config.take_profit_pct, stop_loss_pct=config.stop_loss_pct)
        _runtime["client"] = client
        _runtime["error"] = None
    return status()


def stop():
    with _lock:
        memory.update_settings(enabled=False)
    return status()


def close_position():
    with _lock:
        client = _runtime["client"] or CoinBotDemoClient()
        market = _runtime["market"]
        if not market or market_phase(market) != "trading":
            raise ValueError("No tradable market is past the observation period")
        exposure = memory.exposure(market["ticker"])
        for outcome in ("yes", "no"):
            if exposure[outcome]["count"] >= 1:
                return _order(client, market, outcome, "sell", math.floor(exposure[outcome]["count"]))
        raise ValueError("CoinBot has no open position in this market")


def status():
    with _lock:
        config = memory.settings()
        market = _runtime["market"]
        ticker = market["ticker"] if market else None
        now = datetime.now(timezone.utc)
        remaining = max(0, int((_parse_time(market["close_time"]) - now).total_seconds())) if market else None
        observation_left = max(0, int((_parse_time(market["open_time"]) +
                                      timedelta(seconds=OBSERVATION_SECONDS) - now).total_seconds())) if market else 0
        return {"enabled": bool(config["enabled"]), "configured": bool(os.getenv("COINBOT_DEMO_KEY_ID") and
                os.getenv("COINBOT_DEMO_PRIVATE_KEY_PATH")),
                "config": {key: config[key] for key in ("max_window_spend", "take_profit_pct", "stop_loss_pct")},
                "phase": _runtime["phase"], "market": market, "ticker": ticker,
                "upcoming": _runtime["upcoming"], "seconds_left": remaining,
                "observation_seconds_left": observation_left, "error": _runtime["error"],
                "decision": _runtime["last_decision"], "snapshots": memory.recent_snapshots(ticker, 90) if ticker else [],
                "exposure": memory.exposure(ticker) if ticker else None,
                "orders": memory.orders(limit=30), "equity": memory.equity_today(),
                "rounds": memory.lessons(12)}
