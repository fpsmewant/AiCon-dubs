"""A real Alpaca trade is required before a priced proposal can be created."""

import os
from datetime import datetime, timezone, timedelta
from threading import Lock
from time import monotonic

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestTradeRequest, StockSnapshotRequest, StockBarsRequest
from alpaca.data.enums import DataFeed
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient


WATCHLIST = ('SPY', 'QQQ', 'DIA', 'AAPL', 'MSFT', 'NVDA', 'AMZN', 'TSLA')
_cache = None
_cache_until = 0.0
_lock = Lock()


def snapshot_quote(symbol, snapshot):
    trade = snapshot.latest_trade
    previous = snapshot.previous_daily_bar
    price = float(trade.price) if trade and trade.price > 0 else None
    close = float(previous.close) if previous and previous.close > 0 else None
    return {
        'symbol': symbol, 'price': price,
        'change_pct': (price / close - 1) * 100 if price is not None and close else None,
        'as_of': trade.timestamp.isoformat() if trade else None,
    }


def market_summary():
    """Real IEX snapshots; cache successful responses for 20 seconds only."""
    global _cache, _cache_until
    with _lock:
        if _cache is not None and monotonic() < _cache_until:
            return _cache
        key, secret = os.getenv('ALPACA_API_KEY'), os.getenv('ALPACA_SECRET_KEY')
        if not key or not secret:
            raise RuntimeError('Alpaca credentials are not configured')
        client = StockHistoricalDataClient(key, secret)
        snapshots = client.get_stock_snapshot(StockSnapshotRequest(
            symbol_or_symbols=list(WATCHLIST), feed=DataFeed.IEX))
        clock = TradingClient(key, secret, paper=True).get_clock()
        result = {
            'source': 'Alpaca / IEX', 'is_open': clock.is_open,
            'next_open': clock.next_open.isoformat(),
            'next_close': clock.next_close.isoformat(),
            'fetched_at': datetime.now(timezone.utc).isoformat(),
            'quotes': [snapshot_quote(symbol, snapshots[symbol]) for symbol in WATCHLIST if symbol in snapshots],
        }
        _cache, _cache_until = result, monotonic() + 20
        return result


def latest_price(symbol: str) -> float:
    key, secret = os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY")
    if not key or not secret:
        raise RuntimeError("Alpaca paper API keys are not configured")
    client = StockHistoricalDataClient(key, secret)
    trades = client.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=symbol, feed=DataFeed.IEX))
    price = float(trades[symbol].price)
    if price <= 0:
        raise ValueError("Alpaca returned an invalid latest trade price")
    return price


def daily_history(symbols: list[str], days: int = 45) -> dict:
    key, secret = os.getenv('ALPACA_API_KEY'), os.getenv('ALPACA_SECRET_KEY')
    if not key or not secret:
        raise RuntimeError('Alpaca paper API keys are not configured')
    now = datetime.now(timezone.utc)
    bars = StockHistoricalDataClient(key, secret).get_stock_bars(StockBarsRequest(
        symbol_or_symbols=symbols, timeframe=TimeFrame.Day,
        start=now - timedelta(days=days), end=now, feed=DataFeed.IEX,
    ))
    return {
        symbol: [
            {'date': bar.timestamp.date().isoformat(), 'open': float(bar.open),
             'high': float(bar.high), 'low': float(bar.low), 'close': float(bar.close),
             'volume': float(bar.volume)}
            for bar in bars.data.get(symbol, [])
        ]
        for symbol in symbols
    }
