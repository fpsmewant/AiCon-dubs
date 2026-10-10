"""Alpaca paper trading adapter. Never constructs a live TradingClient."""

import os
from typing import Any

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
from alpaca.trading.requests import LimitOrderRequest, StopLossRequest, TakeProfitRequest

from execution.broker_adapter import IBroker
from intelligence.generators import TradeProposal


class AlpacaClient(IBroker):
    def __init__(self) -> None:
        key = os.getenv("ALPACA_API_KEY")
        secret = os.getenv("ALPACA_SECRET_KEY")
        if not key or not secret:
            raise RuntimeError("Alpaca paper API keys are not configured")
        self.client = TradingClient(key, secret, paper=True)

    def get_account(self) -> dict[str, Any]:
        account = self.client.get_account()
        return {
            "equity": float(account.equity),
            "buying_power": float(account.buying_power),
            "cash": float(account.cash),
            "last_equity": float(account.last_equity),
            "daily_loss": max(0.0, float(account.last_equity) - float(account.equity)),
            "shorting_enabled": bool(account.shorting_enabled),
        }

    def get_positions(self) -> list[dict[str, Any]]:
        return [
            {
                "symbol": position.symbol,
                "qty": float(position.qty),
                "side": str(position.side.value),
                "market_value": float(position.market_value),
                "unrealized_pl": float(position.unrealized_pl),
            }
            for position in self.client.get_all_positions()
        ]

    def place_order(self, proposal: TradeProposal) -> dict[str, Any]:
        common = dict(
            symbol=proposal.symbol,
            qty=proposal.qty,
            side=OrderSide(proposal.side.value),
            time_in_force=TimeInForce.DAY,
            order_class=OrderClass.BRACKET,
            take_profit=TakeProfitRequest(limit_price=round(proposal.take_profit_price, 2)),
            stop_loss=StopLossRequest(stop_price=round(proposal.stop_loss_price, 2)),
        )
        request = LimitOrderRequest(limit_price=round(proposal.target_entry_price, 2), **common)
        order = self.client.submit_order(order_data=request)
        return {"id": str(order.id), "status": str(order.status.value), "symbol": order.symbol}

    def cancel_order(self, order_id: str) -> None:
        self.client.cancel_order_by_id(order_id)
