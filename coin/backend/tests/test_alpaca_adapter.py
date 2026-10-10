from types import SimpleNamespace

from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce

from execution.alpaca_client import AlpacaClient
from tests.test_firewall import proposal


def test_bracket_limit_order_is_submitted_without_network():
    captured = []

    class TradingStub:
        def submit_order(self, order_data):
            captured.append(order_data)
            return SimpleNamespace(id="paper-123", status=SimpleNamespace(value="accepted"), symbol="AAPL")

    broker = AlpacaClient.__new__(AlpacaClient)
    broker.client = TradingStub()
    result = broker.place_order(proposal())
    assert result["id"] == "paper-123"
    assert captured[0].order_class == OrderClass.BRACKET
    assert captured[0].side == OrderSide.BUY
    assert captured[0].limit_price == 100
    assert captured[0].take_profit.limit_price == 110
    assert captured[0].stop_loss.stop_price == 95


def test_recent_orders_are_exposed_without_waiting_for_fills():
    class TradingStub:
        def get_orders(self, filter):
            return [SimpleNamespace(id="paper-123", symbol="AAPL", side=SimpleNamespace(value="buy"),
                                    status=SimpleNamespace(value="accepted"), qty="1", filled_qty="0",
                                    limit_price="100.00", submitted_at=None)]

    broker = AlpacaClient.__new__(AlpacaClient)
    broker.client = TradingStub()
    assert broker.get_recent_orders()[0] == {
        "id": "paper-123", "symbol": "AAPL", "side": "buy", "status": "accepted",
        "qty": 1.0, "filled_qty": 0.0, "limit_price": 100.0, "submitted_at": None,
    }


def test_coinbot_uses_paper_market_bracket_with_broker_exits():
    captured = []

    class TradingStub:
        def submit_order(self, order_data):
            captured.append(order_data)
            return SimpleNamespace(id="bot-123", status=SimpleNamespace(value="accepted"), symbol="NVDA")

    broker = AlpacaClient.__new__(AlpacaClient)
    broker.client = TradingStub()
    result = broker.place_stock_bracket("NVDA", 2, 98, 103)
    assert result["id"] == "bot-123"
    assert captured[0].order_class == OrderClass.BRACKET
    assert captured[0].side == OrderSide.BUY
    assert captured[0].qty == 2
    assert captured[0].time_in_force == TimeInForce.GTC
    assert captured[0].take_profit.limit_price == 103
    assert captured[0].stop_loss.stop_price == 98


def test_coinbot_can_avoid_symbols_with_other_working_orders():
    class TradingStub:
        def get_orders(self, filter):
            assert filter.status.value == "open"
            return [SimpleNamespace(symbol="AAPL"), SimpleNamespace(symbol="TSLA")]

    broker = AlpacaClient.__new__(AlpacaClient)
    broker.client = TradingStub()
    assert broker.get_open_order_symbols() == {"AAPL", "TSLA"}
