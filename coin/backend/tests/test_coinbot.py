"""CoinBot order guards and the learning journal, without account credentials."""

from datetime import datetime, timedelta, timezone

from db import coinbot_memory as memory
from engine import coinbot


def quote(symbol="NVDA", price=100):
    return {"symbol": symbol, "price": price, "change_pct": 1.2,
            "as_of": datetime.now(timezone.utc).isoformat()}


class FakeClient:
    def __init__(self):
        self.orders = []

    def get_positions(self):
        return []

    def get_open_order_symbols(self):
        return set()

    def get_account(self):
        return {"buying_power": 5000, "daily_loss": 0}

    def place_stock_bracket(self, symbol, qty, stop, target):
        self.orders.append((symbol, qty, stop, target))
        return {"id": "paper-1", "status": "accepted", "symbol": symbol}


def test_closed_market_never_sends_an_order(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(coinbot, "market_summary", lambda: {
        "is_open": False, "quotes": [quote()], "next_open": None, "fetched_at": None,
    })
    monkeypatch.setattr(coinbot, "minute_history", lambda *args: [])
    monkeypatch.setattr(coinbot, "_reconcile", lambda *args: None)
    memory.update_settings(enabled=True)
    coinbot.tick(client)
    assert coinbot.status()["phase"] == "market_closed"
    assert not client.orders
    assert not memory.recent_snapshots("NVDA")


def test_risk_budget_respects_mandate_and_whole_share():
    class Mandate:
        max_daily_loss = 100
        max_position_size = 700
        allocated_capital = 3000
        max_loss_per_trade = 10

    budget, reason = coinbot._budget({"max_trade_budget": 1000, "stop_loss_pct": 2},
                                     Mandate(), {"buying_power": 5000, "daily_loss": 0}, 200)
    assert budget == 500
    assert reason is None
    budget, reason = coinbot._budget({"max_trade_budget": 100, "stop_loss_pct": 2},
                                     Mandate(), {"buying_power": 5000, "daily_loss": 0}, 200)
    assert budget == 0
    assert "one share" in reason


def test_recent_losses_block_new_proposal(monkeypatch):
    memory.record_trade("lost-1", "NVDA", 1, 100, 98, 103, "closed")
    memory.update_trade("lost-1", pnl=-2, exit_time=memory.now_iso(), lesson="Loss")
    memory.record_trade("lost-2", "NVDA", 1, 100, 98, 103, "closed")
    memory.update_trade("lost-2", pnl=-2, exit_time=memory.now_iso(), lesson="Loss")
    monkeypatch.setattr(coinbot.gemini_client, "complete", lambda *args, **kwargs:
                        (_ for _ in ()).throw(AssertionError("Model should not be called")))
    decision = coinbot._decide("NVDA", 0.6, quote(),
                              {"take_profit_pct": 3, "stop_loss_pct": 1.5}, 500)
    assert decision["action"] == "WAIT"


def test_entry_and_exit_are_journaled():
    memory.record_trade("paper-1", "AAPL", 2, 100, 98, 103, "accepted")
    memory.update_trade("paper-1", status="filled", filled_qty=2, entry_price=100)
    trade = memory.open_trades()[0]
    result = coinbot._closed(trade, 2, {"filled_avg_price": 100},
                             {"filled_avg_price": 103, "filled_at": memory.now_iso()})
    memory.update_trade("paper-1", **result)
    assert memory.open_trades() == []
    assert memory.lessons("AAPL")[0]["pnl"] == 6
    assert memory.realized_today() == 6


def test_rank_needs_real_observation_span():
    for _ in range(5):
        memory.snapshot("TSLA", 250)
    assert coinbot._rank([quote("TSLA", 250)]) == []
