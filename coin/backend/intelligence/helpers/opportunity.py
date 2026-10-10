"""Transparent watchlist screen and paper position sizing; no automated orders."""

from math import floor


STYLE_FRACTIONS = {
    'capital_preservation': (0.15, 0.03),
    'conservative': (0.25, 0.05),
    'balanced': (0.50, 0.10),
    'growth': (0.65, 0.125),
    'high-risk': (0.75, 0.15),
}


def rank_opportunities(quotes: list[dict], histories: dict, mandate, account: dict) -> list[dict]:
    risk_fraction, capital_fraction = STYLE_FRACTIONS[mandate.risk_style.value]
    positions = account.get('positions', [])
    exposure = sum(abs(float(p.get('market_value', 0))) for p in positions)
    available = max(0, min(mandate.allocated_capital - exposure, float(account.get('buying_power', 0))))
    daily_budget = max(0, mandate.max_daily_loss - float(account.get('daily_loss', 0)))
    candidates = []
    for quote in quotes:
        symbol, price = quote['symbol'], quote.get('price')
        bars = histories.get(symbol, [])[-21:]
        if not price or len(bars) < 21 or bars[0]['close'] <= 0:
            continue
        change = (bars[-1]['close'] / bars[0]['close'] - 1) * 100
        average_range = sum((bar['high'] - bar['low']) / bar['close'] for bar in bars[1:] if bar['close'] > 0) / 20
        if change <= 0 or average_range <= 0:
            continue
        stop_pct = max(0.02, min(0.15, 2 * average_range))
        existing = sum(abs(float(p.get('market_value', 0))) for p in positions if p.get('symbol') == symbol)
        position_budget = max(0, mandate.max_position_size - existing)
        dollar_cap = min(available, position_budget, mandate.allocated_capital * capital_fraction)
        risk_cap = min(mandate.max_loss_per_trade * risk_fraction, daily_budget)
        qty = min(floor(dollar_cap / price), floor(risk_cap / (price * stop_pct)))
        if qty < 1:
            continue
        candidates.append({
            'symbol': symbol, 'price': price, 'as_of': quote.get('as_of'),
            'return_20d_pct': round(change, 2), 'average_daily_range_pct': round(average_range * 100, 2),
            'score': round(change / (average_range * 100), 2), 'shares': qty,
            'estimated_cost': round(price * qty, 2),
            'planned_stop_pct': round(stop_pct * 100, 2),
            'estimated_loss_at_stop': round(qty * price * stop_pct, 2),
        })
    return sorted(candidates, key=lambda item: item['score'], reverse=True)[:5]
