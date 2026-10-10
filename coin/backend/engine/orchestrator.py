"""The sole route from a proposal to a broker order."""

from typing import Any
from concurrent.futures import ThreadPoolExecutor

from execution.broker_adapter import IBroker
from intelligence.agents import bear, bull, judge
from intelligence.data_feeds.market_data import latest_price
from intelligence.generators import ExecutionMode, FirewallVerdict, TradeProposal, UserMandate
from risk.firewall import RiskFirewall


def analyze(symbol: str) -> TradeProposal:
    price = latest_price(symbol)
    data = {"latest_trade_price": price, "source": "Alpaca IEX latest trade"}
    with ThreadPoolExecutor(max_workers=2) as pool:
        bullish = pool.submit(bull.analyze, symbol, data)
        bearish = pool.submit(bear.analyze, symbol, data)
        arguments = bullish.result(), bearish.result()
    return judge.propose(symbol, price, *arguments)


def debate_side(symbol: str, side: str) -> dict:
    price = latest_price(symbol)
    context = {'latest_trade_price': price, 'source': 'Alpaca IEX latest trade'}
    argument = bull.analyze(symbol, context) if side == 'bull' else bear.analyze(symbol, context)
    return {'symbol': symbol, 'side': side, 'argument': argument, 'price': price}


def judge_debate(symbol: str, bull_argument: str, bear_argument: str) -> TradeProposal:
    return judge.propose(symbol, latest_price(symbol), bull_argument, bear_argument)


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
    return {"status": "submitted", "verdict": verdict, "order": order}
