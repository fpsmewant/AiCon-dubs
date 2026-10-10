"""Alpaca paper trading adapter. Never constructs a live TradingClient."""

import os
from typing import Any

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderClass, OrderSide, QueryOrderStatus, TimeInForce
from alpaca.trading.requests import ClosePositionRequest, LimitOrderRequest, MarketOrderRequest, StopLossRequest, TakeProfitRequest, GetOrderByIdRequest, GetOrdersRequest

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

    def get_recent_orders(self) -> list[dict[str, Any]]:
        orders = self.client.get_orders(filter=GetOrdersRequest(
            status=QueryOrderStatus.ALL, limit=20, nested=True))
        return [{
            "id": str(order.id),
            "symbol": order.symbol,
            "side": order.side.value,
            "status": order.status.value,
            "qty": float(order.qty or 0),
            "filled_qty": float(order.filled_qty or 0),
            "limit_price": float(order.limit_price) if order.limit_price else None,
            "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
        } for order in orders]

    def get_open_order_symbols(self) -> set[str]:
        orders = self.client.get_orders(filter=GetOrdersRequest(
            status=QueryOrderStatus.OPEN, limit=500))
        return {order.symbol for order in orders}

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

    def place_stock_bracket(self, symbol: str, qty: int, stop_price: float,
                            target_price: float) -> dict[str, Any]:
        """Market entry with broker-hosted exit legs; paper account only."""
        if qty < 1 or stop_price <= 0 or target_price <= stop_price:
            raise ValueError("Invalid bracket order")
        request = MarketOrderRequest(
            symbol=symbol, qty=qty, side=OrderSide.BUY,
            time_in_force=TimeInForce.GTC, order_class=OrderClass.BRACKET,
            take_profit=TakeProfitRequest(limit_price=round(target_price, 2)),
            stop_loss=StopLossRequest(stop_price=round(stop_price, 2)),
        )
        order = self.client.submit_order(order_data=request)
        return {"id": str(order.id), "status": order.status.value, "symbol": order.symbol}

    def cancel_order(self, order_id: str) -> None:
        self.client.cancel_order_by_id(order_id)

    def close_bot_position(self, symbol: str, qty: int, leg_ids: list[str]) -> dict:
        for leg_id in leg_ids:
            try:
                self.client.cancel_order_by_id(leg_id)
            except Exception:
                # Filled or already cancelled legs are resolved by the caller's reconciliation.
                pass
        order = self.client.close_position(symbol, close_options=ClosePositionRequest(qty=str(qty)))
        return {"id": str(order.id), "status": order.status.value}

    def get_order(self, order_id: str) -> dict:
        order = self.client.get_order_by_id(order_id, filter=GetOrderByIdRequest(nested=True))
        return {"status": order.status.value,
                "filled_at": order.filled_at.isoformat() if order.filled_at else None,
                "filled_avg_price": float(order.filled_avg_price) if order.filled_avg_price else None,
                "filled_qty": float(order.filled_qty or 0),
                "legs": [{"status": leg.status.value,
                          "id": str(leg.id),
                          "side": leg.side.value,
                          "filled_at": leg.filled_at.isoformat() if leg.filled_at else None,
                          "filled_avg_price": float(leg.filled_avg_price) if leg.filled_avg_price else None}
                         for leg in order.legs or []]}
