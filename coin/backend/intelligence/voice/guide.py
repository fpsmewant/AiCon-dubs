"""Turns an investing question into a bounded page-navigation plan."""

import json
import os
import re

from pydantic import BaseModel, Field, field_validator

from intelligence.agents.openrouter_client import complete


INVESTING_TERMS = re.compile(
    r"\b(invest|investment|stock|stocks|share|shares|portfolio|market|risk|"
    r"short[ -]?term|long[ -]?term|stable|stability|buy|allocation|allocate|etf|fund)\b",
    re.IGNORECASE,
)
ALLOWED_STEPS = {"opportunities", "price_history", "research", "risk_mandate"}


class GuidePlan(BaseModel):
    valid: bool
    spoken_summary: str = Field(min_length=1, max_length=700)
    horizon: str = Field(pattern=r"^(short_term|long_term|unspecified)$")
    budget: float | None = Field(default=None, gt=0, le=10_000_000)
    symbols: list[str] = Field(default_factory=list, max_length=3)
    steps: list[str] = Field(default_factory=list, max_length=4)
    key_points: list[str] = Field(default_factory=list, max_length=4)

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


def build_guide(prompt: str, candidates: list[dict], histories: dict) -> GuidePlan:
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
    instruction = f"""You are Coin's guided investing workspace, not a chatbot and not a financial adviser.
User request: {prompt}
Available screen evidence: {json.dumps(evidence)}
Return only JSON with valid, spoken_summary, horizon, budget, symbols, steps, key_points.
Only use symbols in the evidence. Guide the user through comparing charts and risk, using cautious language.
Never promise returns or call anything the best investment. For dollar budgets, never suggest spending more than the budget.
steps may contain only: opportunities, price_history, research, risk_mandate.
spoken_summary must be under 90 words. key_points must be short and evidence-based.
If the request is unrelated to investing, valid=false and explain that briefly."""
    try:
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
            steps=["opportunities", "price_history", "research", "risk_mandate"],
            key_points=[
                f"{item['symbol']}: {item['return_20d_pct']}% over 20 sessions with {item['average_daily_range_pct']}% average daily range."
                for item in top
            ],
        )
    allowed = {item["symbol"] for item in candidates}
    plan.symbols = [symbol for symbol in plan.symbols if symbol in allowed][:3]
    plan.steps = [step for step in plan.steps if step in ALLOWED_STEPS]
    return plan
