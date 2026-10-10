from datetime import datetime, timedelta, timezone

from db import coinbot_memory as memory
from engine import coinbot


def market(opened):
    return {"ticker": "KXBTC15M-TEST", "title": "BTC up?", "open_time": opened.isoformat(),
            "close_time": (opened + timedelta(minutes=15)).isoformat(),
            "yes_bid_dollars": "0.4800", "yes_ask_dollars": "0.5200",
            "no_bid_dollars": "0.4800", "no_ask_dollars": "0.5200", "volume_fp": "100"}


def test_first_two_minutes_cannot_place_order(monkeypatch):
    opened = datetime.now(timezone.utc) - timedelta(seconds=60)
    sample = market(opened)
    calls = []

    class FakeClient:
        def markets(self, status="open"):
            return [sample]

        def market(self, ticker):
            return sample

        def balance(self):
            return {"balance": 10000, "portfolio_value": 0}

        def order(self, **kwargs):
            calls.append(kwargs)
            raise AssertionError("Order attempted during observation period")

    monkeypatch.setattr(coinbot, "_spot", lambda: 80000)
    monkeypatch.setattr(coinbot, "_runtime", {"phase": "idle", "market": None, "error": None,
        "last_decision": None, "last_decision_at": 0.0, "last_equity_at": 0.0,
        "last_discovery_at": 0.0, "current_ticker": None, "upcoming": None, "client": None,
        "last_settlement_at": 0.0})
    memory.update_settings(enabled=True)
    coinbot.tick(FakeClient(), opened + timedelta(seconds=60))
    assert coinbot._runtime["phase"] == "observing"
    assert len(memory.recent_snapshots(sample["ticker"])) == 1
    assert calls == []


def test_demo_market_filter_and_round_memory():
    opened = datetime.now(timezone.utc) - timedelta(minutes=3)
    current, upcoming = coinbot._select_market([market(opened),
        market(opened + timedelta(minutes=15)),
        market(opened - timedelta(days=1))])
    assert current["ticker"] == "KXBTC15M-TEST"
    assert upcoming is not None
    memory.record_order("buy-1", "KXBTC15M-TEST", "yes", "buy", 2, .52)
    memory.record_order("sell-1", "KXBTC15M-TEST", "yes", "sell", 1, .65)
    assert memory.exposure("KXBTC15M-TEST")["yes"]["count"] == 1
    assert memory.exposure("KXBTC15M-TEST")["spent"] == 1.04


def test_demo_host_is_required(monkeypatch):
    from execution.kalshi_demo import CoinBotDemoClient
    monkeypatch.setenv("COINBOT_DEMO_BASE_URL", "https://external-api.kalshi.com/trade-api/v2")
    try:
        CoinBotDemoClient()
    except ValueError as exc:
        assert "demo" in str(exc)
    else:
        raise AssertionError("Production endpoint was accepted")
