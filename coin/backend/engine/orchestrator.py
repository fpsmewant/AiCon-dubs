"""The sole route from a proposal to a broker order."""

from typing import Any
import json
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from threading import Lock
from time import monotonic

from execution.broker_adapter import IBroker
from intelligence.agents import bear, bull, judge
from intelligence.data_feeds.market_data import latest_price, market_snapshot
from intelligence.data_feeds.marketaux import cached_news
from intelligence.rag import relevant_context
from db import learning_memory
from intelligence.generators import ExecutionMode, FirewallVerdict, TradeProposal, UserMandate
from risk.firewall import RiskFirewall


_pool = ThreadPoolExecutor(max_workers=4)
_prefetch: dict[str, tuple[float, Future]] = {}
_progress: dict[str, dict] = {}
_prefetch_lock = Lock()


def _debate(symbol: str) -> dict:
    price = latest_price(symbol)
    news = cached_news(symbols=symbol, countries="", limit=5)["articles"]
    memory = relevant_context(f"{symbol} US stock market company recent news historical trades", limit=3)
    sources = {'alpaca': True, 'marketaux': len(news), 'liquid': len(memory)}
    data = {"latest_trade_price": price, "source": "Alpaca IEX latest trade",
            "recent_news": news, 'retrieved_memory': memory}
    with _prefetch_lock:
        _progress[symbol] = {'price': price, 'sources': sources}
    with ThreadPoolExecutor(max_workers=2) as pool:
        tasks = {pool.submit(bull.analyze, symbol, data): 'bull',
                 pool.submit(bear.analyze, symbol, data): 'bear'}
        result = {"symbol": symbol, "price": price, "news": news, 'sources': sources}
        for future in as_completed(tasks):
            side = tasks[future]
            result[side] = future.result()
            with _prefetch_lock:
                _progress[symbol] = dict(result)
        return result


def prefetch_debate(symbol: str) -> dict:
    with _prefetch_lock:
        for key, (started, _) in list(_prefetch.items()):
            if monotonic() - started >= 120:
                _prefetch.pop(key, None)
                _progress.pop(key, None)
        if len(_prefetch) >= 64 and symbol not in _prefetch:
            return {'symbol': symbol, 'status': 'busy'}
        cached = _prefetch.get(symbol)
        if cached and monotonic() - cached[0] < 120:
            future = cached[1]
        else:
            future = _pool.submit(_debate, symbol)
            _prefetch[symbol] = (monotonic(), future)
    return debate_state(symbol)


def debate_state(symbol: str) -> dict:
    with _prefetch_lock:
        cached = _prefetch.get(symbol)
    if not cached or monotonic() - cached[0] >= 120:
        return {"symbol": symbol, "status": "idle"}
    future = cached[1]
    if not future.done():
        with _prefetch_lock:
            progress = dict(_progress.get(symbol, {}))
        return {"symbol": symbol, "status": "running", **progress}
    try:
        return {"symbol": symbol, "status": "complete", **future.result()}
    except Exception:
        return {"symbol": symbol, "status": "failed"}


def _snapshot(symbol: str, at: datetime | None = None) -> dict:
    result = market_snapshot(symbol, at)
    articles = cached_news(symbols=symbol, countries="", limit=5)["articles"]
    if at:
        articles = [item for item in articles if item.get('published_at') and datetime.fromisoformat(item['published_at'].replace('Z', '+00:00')) <= at]
    scores = [item["sentiment_score"] for item in articles if item.get("sentiment_score") is not None]
    result["sentiment_score"] = round(sum(scores) / len(scores), 4) if scores else None
    return result


def refresh_due_trades() -> None:
    for row in learning_memory.due_trades():
        try:
            at = datetime.fromisoformat(row['submitted_at']) + timedelta(minutes=30)
            post = _snapshot(row["symbol"], at)
            learning_memory.score_trade(row["order_id"], post)
        except Exception:
            continue


def sync_learning(broker=None) -> None:
    """Reconcile fills/exits; durable pending records also survive server restarts."""
    rows = learning_memory.open_trades()
    if rows:
        if broker is None:
            from execution.alpaca_client import AlpacaClient
            broker = AlpacaClient()
        for row in rows:
            try:
                order = broker.get_order(row['order_id'])
                if order['status'] in ('canceled', 'expired', 'rejected'):
                    learning_memory.cancel_pending(row['order_id'])
                if order.get('filled_at') and row['status'] == 'pending':
                    at = datetime.fromisoformat(order['filled_at'])
                    try:
                        pre = _snapshot(row['symbol'], at - timedelta(minutes=30))
                    except Exception:
                        pre = {'price': None, 'volume': None, 'volatility': None,
                               'sentiment_score': None, 'source': 'unavailable'}
                    learning_memory.update_fill(row['order_id'], order['filled_avg_price'], order['filled_qty'], at, pre)
                exit_leg = next((leg for leg in order.get('legs', []) if leg.get('filled_at')), None)
                if exit_leg:
                    at = datetime.fromisoformat(exit_leg['filled_at'])
                    try:
                        snapshot = _snapshot(row['symbol'], at)
                    except Exception:
                        snapshot = {'source': 'Alpaca exit fill', 'as_of': at.isoformat()}
                    snapshot['price'] = exit_leg['filled_avg_price']
                    post = json.loads(row['post_snapshot']) if row['post_snapshot'] else None
                    learning_memory.score_trade(row['order_id'], post, snapshot)
            except Exception:
                continue
    refresh_due_trades()


def analyze(symbol: str) -> TradeProposal:
    cached = debate_state(symbol)
    if cached['status'] == 'running':
        with _prefetch_lock:
            future = _prefetch[symbol][1]
        result = future.result()
    else:
        result = cached if cached["status"] == "complete" else _debate(symbol)
    return judge_debate(symbol, result["bull"], result["bear"],
                        price=result["price"], news=result["news"])


def debate_side(symbol: str, side: str) -> dict:
    state = debate_state(symbol)
    if state.get(side):
        return {'symbol': symbol, 'side': side, 'argument': state[side], 'price': state['price']}
    price = latest_price(symbol)
    news = cached_news(symbols=symbol, countries="", limit=5)["articles"]
    context = {'latest_trade_price': price, 'source': 'Alpaca IEX latest trade', 'recent_news': news}
    argument = bull.analyze(symbol, context) if side == 'bull' else bear.analyze(symbol, context)
    return {'symbol': symbol, 'side': side, 'argument': argument, 'price': price}


def judge_debate(symbol: str, bull_argument: str, bear_argument: str,
                 price: float | None = None, news: list[dict] | None = None) -> TradeProposal:
    news = news if news is not None else cached_news(symbols=symbol, countries="", limit=5)["articles"]
    price = price if price is not None else latest_price(symbol)
    try:
        refresh_due_trades()
        snapshot = _snapshot(symbol)
        lessons = learning_memory.similar_losses(symbol, snapshot)
    except Exception:
        lessons = []
    return judge.propose(symbol, price, bull_argument, bear_argument, news=news, lessons=lessons)


def account_snapshot(broker: IBroker) -> dict[str, Any]:
    account = broker.get_account()
    positions = broker.get_positions()
    account["positions"] = positions
    account["unrealized_pl"] = sum(float(p.get("unrealized_pl", 0)) for p in positions)
    return account


def review(proposal: TradeProposal, mandate: UserMandate, broker: IBroker) -> FirewallVerdict:
    return RiskFirewall().validate(proposal, mandate, account_snapshot(broker))


def execute(proposal: TradeProposal, mandate: UserMandate, broker: IBroker, approved: bool = False) -> dict[str, Any]:
    verdict = review(proposal, mandate, broker)
    if not verdict.passed:
        return {"status": "rejected", "verdict": verdict, "order": None}
    if mandate.auto_execution_mode == ExecutionMode.observe:
        return {"status": "observed", "verdict": verdict, "order": None}
    if mandate.auto_execution_mode == ExecutionMode.recommend_approve and not approved:
        return {"status": "awaiting_approval", "verdict": verdict, "order": None}
    order = broker.place_order(proposal)
    # Capture historical observations after submission so market fetches cannot delay approval.
    pre = {"price": None, "volume": None, "volatility": None,
           "sentiment_score": None, "source": "awaiting_fill_snapshot"}
    try:
        learning_memory.record_trade(str(order["id"]), proposal, pre,
                                     status='pending' if hasattr(broker, 'get_order') else 'filled')
        learning_status = 'recorded'
    except Exception:
        # An accepted broker order must never be reported as a failed order due to local memory.
        learning_status = 'unavailable'
    return {"status": "submitted", "verdict": verdict, "order": order, "learning_status": learning_status}
