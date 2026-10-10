"""Turns an investing question into a bounded page-navigation plan."""

import json
import os
import re

from pydantic import BaseModel, Field, field_validator

from intelligence.agents.openrouter_client import complete
from intelligence.agents.gemini_client import complete as gemini_complete


INVESTING_TERMS = re.compile(
    r"\b(invest|investment|stock|stocks|share|shares|portfolio|market|risk|"
    r"short[ -]?term|long[ -]?term|stable|stability|buy|allocation|allocate|etf|fund)\b",
    re.IGNORECASE,
)
ALLOWED_STEPS = {"opportunities", "market_news", "price_history", "research", "risk_mandate"}


class GuidePlan(BaseModel):
    valid: bool
    spoken_summary: str = Field(min_length=1, max_length=700)
    horizon: str = Field(pattern=r"^(short_term|long_term|unspecified)$")
    budget: float | None = Field(default=None, gt=0, le=10_000_000)
    symbols: list[str] = Field(default_factory=list, max_length=3)
    steps: list[str] = Field(default_factory=list, max_length=5)
    key_points: list[str] = Field(default_factory=list, max_length=4)
    news_points: list[str] = Field(default_factory=list, max_length=4)
    allocations: list[dict] = Field(default_factory=list, max_length=3)

    @field_validator("symbols")
    @classmethod
    def normalize_symbols(cls, value: list[str]) -> list[str]:
        return [symbol.strip().upper() for symbol in value if re.fullmatch(r"[A-Za-z][A-Za-z0-9.\-]{0,11}", symbol.strip())]


def invalid_plan() -> GuidePlan:
    return GuidePlan(
        valid=False,
        spoken_summary="That request is outside Coin's investing guide. Ask about stocks, risk, a budget, or a short or long time horizon.",
        horizon="unspecified",
    )


def prompt_budget(prompt: str) -> float | None:
    match = re.search(r"(?:\$\s*([\d,]+(?:\.\d{1,2})?)|([\d,]+(?:\.\d{1,2})?)\s*(?:dollars?|usd))", prompt, re.IGNORECASE)
    if not match:
        return None
    return float((match.group(1) or match.group(2)).replace(",", ""))


def bounded_allocations(symbols: list[str], budget: float | None, candidates: list[dict]) -> list[dict]:
    if not budget or not symbols:
        return []
    lookup = {item["symbol"]: item for item in candidates}
    selected = [lookup[symbol] for symbol in symbols if symbol in lookup]
    if not selected:
        return []
    inverse_ranges = [1 / max(item["average_daily_range_pct"], 0.1) for item in selected]
    total_weight = sum(inverse_ranges)
    remaining = round(budget, 2)
    allocations = []
    for index, (item, weight) in enumerate(zip(selected, inverse_ranges)):
        amount = remaining if index == len(selected) - 1 else round(budget * weight / total_weight, 2)
        remaining = round(remaining - amount, 2)
        allocations.append({
            "symbol": item["symbol"],
            "amount": amount,
            "percent": round(amount / budget * 100, 1),
            "fractional_shares_reference": round(amount / item["price"], 4),
        })
    return allocations


def build_guide(prompt: str, candidates: list[dict], histories: dict, news: list[dict] | None = None) -> GuidePlan:
    prompt = prompt.strip()
    if not prompt or len(prompt) > 500 or not INVESTING_TERMS.search(prompt):
        return invalid_plan()

    evidence = []
    for item in candidates[:5]:
        history = histories.get(item["symbol"], [])
        evidence.append({
            "symbol": item["symbol"],
            "price": item["price"],
            "return_20d_pct": item["return_20d_pct"],
            "average_daily_range_pct": item["average_daily_range_pct"],
            "risk_sized_shares": item["shares"],
            "risk_sized_cost": item["estimated_cost"],
            "history_start": history[0]["date"] if history else None,
            "history_end": history[-1]["date"] if history else None,
        })
    news_evidence = [{"title": item.get("title"), "source": item.get("source"),
                      "published_at": item.get("published_at"), "symbols": item.get("symbols", []),
                      "sentiment_score": item.get("sentiment_score")} for item in (news or [])[:8]]
    instruction = f"""You are Coin's overall reasoning brain for a guided investing workspace, not a chatbot and not a financial adviser.
User request: {prompt}
Available screen evidence: {json.dumps(evidence)}
Recent cached Marketaux news: {json.dumps(news_evidence)}
Return only JSON with valid, spoken_summary, horizon, budget, symbols, steps, key_points, news_points.
Only use symbols in the evidence. Guide the user through comparing charts and risk, using cautious language.
Never promise returns or call anything the best investment. For dollar budgets, never suggest spending more than the budget.
Separate historical observations from newly fetched news. Never infer facts beyond the supplied headlines.
steps may contain only: opportunities, market_news, price_history, research, risk_mandate.
spoken_summary must be under 90 words. key_points must be short and evidence-based.
If the request is unrelated to investing, valid=false and explain that briefly."""
    try:
        try:
            response = gemini_complete(instruction, temperature=0.1, json_mode=True)
        except Exception:
            response = complete(
                instruction,
                temperature=0.1,
                json_mode=True,
                model=os.getenv("OPENROUTER_GUIDE_MODEL", "liquid/lfm-2.5-2.6b:free"),
                key_env="OPENROUTER_GUIDE_API_KEY",
            )
        plan = GuidePlan.model_validate(json.loads(response))
    except Exception:
        top = candidates[:3]
        if not top:
            return GuidePlan(
                valid=True,
                spoken_summary="Your saved limits currently leave no watchlist candidate to compare. Review the risk mandate first.",
                horizon="unspecified",
                steps=["risk_mandate"],
            )
        plan = GuidePlan(
            valid=True,
            spoken_summary="Let's compare the strongest recent watchlist candidates, inspect their daily charts, then review your risk limits before considering a paper trade.",
            horizon="unspecified",
            symbols=[item["symbol"] for item in top],
            steps=["opportunities", "market_news", "price_history", "research", "risk_mandate"],
            key_points=[
                f"{item['symbol']}: {item['return_20d_pct']}% over 20 sessions with {item['average_daily_range_pct']}% average daily range."
                for item in top
            ],
        )
    allowed = {item["symbol"] for item in candidates}
    plan.symbols = [symbol for symbol in plan.symbols if symbol in allowed][:3]
    plan.steps = [step for step in plan.steps if step in ALLOWED_STEPS]
    detected_budget = prompt_budget(prompt)
    plan.budget = detected_budget or plan.budget
    plan.allocations = bounded_allocations(plan.symbols, plan.budget, candidates)
    if not plan.news_points and news:
        plan.news_points = [f"{item['source']}: {item['title']}" for item in news[:3]]
    return plan
