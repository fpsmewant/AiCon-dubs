"""Evidence-grounded visual voice response for the guided workspace."""

import json
import os
import re
from math import floor

from pydantic import BaseModel, Field

from intelligence.agents.openrouter_client import complete
from intelligence.data_feeds.market_data import daily_history, WATCHLIST
from intelligence.data_feeds.marketaux import cached_news
from intelligence.rag import relevant_context
from intelligence.voice.guide import INVESTING_TERMS, prompt_budget
from intelligence.generators import TradeProposal, UserMandate
from engine import orchestrator

NAMES = {"nvidia": "NVDA", "apple": "AAPL", "microsoft": "MSFT", "amazon": "AMZN",
         "tesla": "TSLA", "google": "GOOGL", "alphabet": "GOOGL", "meta": "META"}


def mentioned_symbol(text: str) -> str | None:
    for name, symbol in NAMES.items():
        if re.search(rf"\b{re.escape(name)}\b", text, re.I):
            return symbol
    for symbol in WATCHLIST:
        if re.search(rf'\b{symbol}\b', text, re.I):
            return symbol
    tokens = re.findall(r"\b[A-Z]{2,5}\b", text)
    stop = {"US", "USD", "AI", "ETF", "THE", "WHAT", "HOW", "ABOUT", "BUY", "STOCK", "TODAY", "API"}
    return next((token for token in tokens if token not in stop), None)


class VisualAnswer(BaseModel):
    speech_text: str
    ticker: str | None = None
    requested_amount: float | None = None
    chart_data: list[dict] = Field(default_factory=list)
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    firewall_status: dict = Field(default_factory=lambda: {"passed": False, "reasons": ["No trade proposal"]})
    proposal: TradeProposal | None = None
    context: list[dict] = Field(default_factory=list)


class AnswerText(BaseModel):
    speech_text: str = Field(min_length=1, max_length=700)
    pros: list[str] = Field(default_factory=list, max_length=3)
    cons: list[str] = Field(default_factory=list, max_length=3)


def answer(prompt: str, mandate: UserMandate | None = None, broker=None) -> VisualAnswer:
    prompt = prompt.strip()
    if not INVESTING_TERMS.search(prompt) and not mentioned_symbol(prompt):
        return VisualAnswer(speech_text="Ask me about a US stock, market news, or a trading budget.")
    symbol = mentioned_symbol(prompt)
    amount = prompt_budget(prompt)
    articles = cached_news(countries="us", symbols=symbol or "", limit=8)["articles"]
    context = relevant_context(prompt)
    bars = daily_history([symbol], days=30)[symbol][-30:] if symbol else []
    evidence = {"recent_news": [{"title": a["title"], "sentiment_score": a.get("sentiment_score")}
                                for a in articles], "retrieved_notes": context,
                "last_price": bars[-1]["close"] if bars else None}
    instruction = ("You are Coin, a concise US market guide. Reply ONLY JSON with speech_text, pros, cons. "
                   "Use at most 3 short points in each array. State uncertainty. Never invent a price, news item, "
                   "or guaranteed return. User: " + prompt + " Evidence: " + json.dumps(evidence))
    try:
        raw = AnswerText.model_validate_json(complete(instruction, json_mode=True, key_env="LIQUID_API_KEY",
                                  model=os.getenv('LIQUID_CHAT_MODEL', 'liquid/lfm-2.5-2.6b:free'))).model_dump()
    except Exception:
        raw = {"speech_text": f"Here is the available market context for {symbol or 'US stocks'}. Review the chart and news before deciding.",
               "pros": [a["title"] for a in articles if (a.get("sentiment_score") or 0) > 0][:3],
               "cons": [a["title"] for a in articles if (a.get("sentiment_score") or 0) < 0][:3]}
    proposal = None
    firewall = {"passed": False, "reasons": ["Save trading limits and request a dollar amount to review an order"]}
    if symbol and amount and mandate and broker:
        try:
            proposal = orchestrator.analyze(symbol)
            quantity = floor(amount / proposal.target_entry_price * 1_000_000) / 1_000_000
            proposal = TradeProposal.model_validate(proposal.model_dump() | {'qty': quantity})
            verdict = orchestrator.review(proposal, mandate, broker)
            firewall = {"passed": verdict.passed, "reasons": verdict.rejected_reasons}
        except Exception:
            firewall = {"passed": False, "reasons": ["Live trade review is unavailable"]}
    return VisualAnswer(speech_text=str(raw.get("speech_text") or "Review the available evidence.")[:700],
                        ticker=symbol, requested_amount=amount, chart_data=bars,
                        pros=[str(x) for x in raw.get("pros", [])][:3],
                        cons=[str(x) for x in raw.get("cons", [])][:3],
                        firewall_status=firewall, proposal=proposal, context=context)
