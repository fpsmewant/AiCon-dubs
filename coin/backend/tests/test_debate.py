from threading import Event

from engine import orchestrator


def test_debate_runs_both_perspectives_before_judging(monkeypatch):
    bull_started, bear_started = Event(), Event()

    def bull(symbol, data):
        bull_started.set()
        assert bear_started.wait(2), 'Bear should start before bull finishes'
        return 'bull argument'

    def bear(symbol, data):
        bear_started.set()
        assert bull_started.wait(2)
        return 'bear argument'

    monkeypatch.setattr(orchestrator, 'latest_price', lambda symbol: 100)
    monkeypatch.setattr(orchestrator.bull, 'analyze', bull)
    monkeypatch.setattr(orchestrator.bear, 'analyze', bear)
    monkeypatch.setattr(orchestrator, 'cached_news', lambda **kwargs: {'articles': []})
    monkeypatch.setattr(orchestrator.judge, 'propose', lambda *args, **kwargs: args)
    assert orchestrator.analyze('AAPL') == ('AAPL', 100, 'bull argument', 'bear argument')
