from datetime import datetime, timedelta, timezone

from db import learning_memory as memory
from intelligence import embeddings
from intelligence.agents import judge
from tests.test_firewall import proposal


def test_pre_post_snapshots_due_and_loss_lookup(tmp_path, monkeypatch):
    monkeypatch.setattr(memory, 'PATH', tmp_path / 'memory.sqlite3')
    now = datetime.now(timezone.utc)
    snapshot = {'price': 100, 'volume': 5000, 'volatility': 0.02, 'sentiment_score': -0.2}
    memory.record_trade('trade-1', proposal(), snapshot, now)
    assert memory.due_trades(now + timedelta(minutes=29)) == []
    assert memory.due_trades(now + timedelta(minutes=30))[0]['order_id'] == 'trade-1'
    assert memory.score_trade('trade-1', snapshot | {'price': 95})['outcome'] == 'BAD'
    assert memory.due_trades(now + timedelta(minutes=31)) == []
    assert memory.similar_losses('AAPL', snapshot)[0]['return_pct'] < 0
    assert memory.similar_losses('NVDA', snapshot) == []
    assert memory.score_trade('trade-1', snapshot | {'price': 95}, snapshot | {'price': 110})['outcome'] == 'GOOD'


def test_losing_lessons_lower_judge_confidence(monkeypatch):
    import json
    monkeypatch.setattr(judge, 'gemini_complete', lambda *a, **kw: json.dumps({
        'judge_summary': 'Review the setup', 'confidence_score': 0.9,
        'estimated_upside_pct': 4, 'estimated_downside_pct': 2}))
    trade = judge.propose('AAPL', 100, 'Bull', 'Bear', lessons=[{'return_pct': -3}])
    assert trade.confidence_score <= 0.35
    assert 'lost money' in trade.judge_summary


def test_liquid_vector_retrieval_and_cached_documents(tmp_path, monkeypatch):
    monkeypatch.setattr(embeddings, 'PATH', tmp_path / 'vectors.sqlite3')
    monkeypatch.setenv('LIQUID_EMBEDDING_MODEL', 'liquid-test')
    calls = []
    def embed(text):
        calls.append(text)
        return [1.0, 0.0] if 'tech' in text else [0.0, 1.0]
    monkeypatch.setattr(embeddings, 'embed', embed)
    embeddings.store_document('news', 'tech stocks rally', 'NVDA')
    embeddings.store_document('news', 'banks fall', 'JPM')
    embeddings.store_document('news', 'tech stocks rally', 'NVDA')
    assert len(calls) == 2
    matches = embeddings.search('tech today')
    assert matches[0]['symbol'] == 'NVDA'
    assert matches[0]['score'] == 1.0


def test_unfilled_orders_are_not_scored_and_actual_fill_time_controls_snapshots(monkeypatch):
    from engine import orchestrator
    now = datetime.now(timezone.utc)
    trade = proposal()
    memory.record_trade('pending', trade, {}, now - timedelta(hours=1), status='pending')
    assert memory.due_trades(now) == []
    captures = []
    def snapshot(symbol, at=None):
        captures.append(at)
        return {'price': 101, 'volume': 2000, 'volatility': 0.01, 'sentiment_score': 0.2}
    monkeypatch.setattr(orchestrator, '_snapshot', snapshot)
    class Broker:
        def get_order(self, order_id):
            return {'status': 'filled', 'filled_at': now.isoformat(), 'filled_avg_price': 101,
                    'filled_qty': 10, 'legs': []}
    orchestrator.sync_learning(Broker())
    assert captures == [now - timedelta(minutes=30)]
    assert memory.open_trades()[0]['entry'] == 101
    assert memory.due_trades(now + timedelta(minutes=29)) == []
    assert memory.due_trades(now + timedelta(minutes=30))[0]['order_id'] == 'pending'
