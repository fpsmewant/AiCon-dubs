from intelligence.generators import UserMandate
from intelligence.helpers.opportunity import rank_opportunities


def test_screen_respects_exposure_daily_loss_and_whole_shares():
    mandate = UserMandate(allocated_capital=2000, risk_style='balanced',
                          max_loss_per_trade=100, max_daily_loss=100,
                          max_position_size=200, auto_execution_mode='observe')
    bars = [{'close': 90 + n, 'high': 92 + n, 'low': 88 + n} for n in range(21)]
    quote = [{'symbol': 'AAPL', 'price': 110, 'as_of': '2026-10-09T20:00:00Z'}]
    account = {'positions': [], 'buying_power': 2000, 'daily_loss': 0}
    result = rank_opportunities(quote, {'AAPL': bars}, mandate, account)
    assert len(result) == 1
    assert result[0]['shares'] == 1
    assert result[0]['estimated_cost'] == 110
    assert rank_opportunities(quote, {'AAPL': bars}, mandate, {**account, 'daily_loss': 100}) == []
    assert rank_opportunities(quote, {'AAPL': bars}, mandate, {**account, 'positions': [{'symbol': 'AAPL', 'market_value': 200}]}) == []
