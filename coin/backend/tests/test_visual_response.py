import json

from intelligence.voice import response
from tests.test_firewall import mandate, proposal, FakeBroker


def test_visual_response_budget_chart_and_firewall(monkeypatch):
    monkeypatch.setattr(response, 'cached_news', lambda **kw: {'articles': []})
    monkeypatch.setattr(response, 'relevant_context', lambda prompt: [{'text': 'GPU context'}])
    monkeypatch.setattr(response, 'daily_history', lambda symbols, **kw: {'NVDA': [{'date': '2026-10-09', 'close': 100}]})
    monkeypatch.setattr(response, 'complete', lambda *args, **kw: json.dumps({
        'speech_text': 'Review Nvidia’s chart and your limits.', 'pros': ['GPU demand'], 'cons': ['Volatility']}))
    monkeypatch.setattr(response.orchestrator, 'analyze', lambda symbol: proposal(symbol=symbol))
    result = response.answer('Should I invest $100 in Nvidia?', mandate(), FakeBroker())
    assert result.ticker == 'NVDA'
    assert result.requested_amount == 100
    assert result.proposal.qty == 1
    assert result.chart_data[0]['close'] == 100
    assert result.firewall_status['passed'] is True
    assert result.context[0]['text'] == 'GPU context'


def test_ticker_mentions_support_names_and_lowercase_tickers():
    assert response.mentioned_symbol('What about Nvidia?') == 'NVDA'
    assert response.mentioned_symbol('buy nvda') == 'NVDA'
    assert response.mentioned_symbol('Apple today') == 'AAPL'
    assert response.mentioned_symbol('What is C++?') is None
