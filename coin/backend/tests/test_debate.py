from threading import Event
from time import monotonic, sleep

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


def test_prefetch_reuses_work_and_exposes_each_finished_analyst(monkeypatch):
    release = Event()
    calls = []
    monkeypatch.setattr(orchestrator, '_prefetch', {})
    monkeypatch.setattr(orchestrator, '_progress', {})
    monkeypatch.setattr(orchestrator, 'latest_price', lambda symbol: 100)
    monkeypatch.setattr(orchestrator, 'cached_news', lambda **kw: {'articles': []})
    def bull(symbol, data):
        calls.append(symbol)
        return 'bull ready'
    def bear(symbol, data):
        assert release.wait(3)
        return 'bear ready'
    monkeypatch.setattr(orchestrator.bull, 'analyze', bull)
    monkeypatch.setattr(orchestrator.bear, 'analyze', bear)
    try:
        orchestrator.prefetch_debate('NVDA')
        future = orchestrator._prefetch['NVDA'][1]
        deadline = monotonic() + 2
        state = orchestrator.debate_state('NVDA')
        while not state.get('bull') and monotonic() < deadline:
            sleep(0.01)
            state = orchestrator.debate_state('NVDA')
        assert state['status'] == 'running'
        assert state['bull'] == 'bull ready'
        orchestrator.prefetch_debate('NVDA')
        assert orchestrator._prefetch['NVDA'][1] is future
        assert calls == ['NVDA']
    finally:
        release.set()
        future.result(timeout=3)
    assert orchestrator.debate_state('NVDA')['status'] == 'complete'
