from datetime import datetime, timezone
from types import SimpleNamespace

from intelligence.data_feeds.market_data import snapshot_quote


def test_market_change_uses_previous_close_and_preserves_timestamp():
    timestamp = datetime(2026, 10, 9, 20, tzinfo=timezone.utc)
    snapshot = SimpleNamespace(latest_trade=SimpleNamespace(price=110, timestamp=timestamp),
                               previous_daily_bar=SimpleNamespace(close=100))
    quote = snapshot_quote('AAPL', snapshot)
    assert round(quote['change_pct'], 6) == 10
    assert quote['as_of'] == timestamp.isoformat()


def test_missing_quotes_do_not_invent_prices_or_changes():
    quote = snapshot_quote('AAPL', SimpleNamespace(latest_trade=None, previous_daily_bar=None))
    assert quote['price'] is None
    assert quote['change_pct'] is None
    assert quote['as_of'] is None
