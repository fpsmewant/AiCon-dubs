from types import SimpleNamespace

from alpaca.trading.enums import OrderClass, OrderSide

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
