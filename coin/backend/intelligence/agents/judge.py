"""Judge yields schema-checked terms; invalid model output uses conservative defaults."""

import json

from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel, Field

from intelligence.generators import TradeProposal
from intelligence.agents.openrouter_client import complete
from intelligence.agents.gemini_client import complete as gemini_complete


class JudgeTerms(BaseModel):
    judge_summary: str = Field(min_length=1)
    confidence_score: float = Field(ge=0, le=1)
    estimated_upside_pct: float = Field(gt=0, le=100)
    estimated_downside_pct: float = Field(gt=0, le=100)


PROMPT = PromptTemplate.from_template(
    "You are a cautious trade judge. Symbol: {symbol}. Latest Alpaca trade: ${price}. Bull: {bull}. Bear: {bear}. "
    "Return ONLY JSON with judge_summary, confidence_score (0 to 1), estimated_upside_pct and estimated_downside_pct "
    "(positive percentages). Use a low confidence when evidence is missing. Do not invent facts."
)


def propose(symbol: str, price: float, bull: str, bear: str, news: list[dict] | None = None,
            lessons: list[dict] | None = None) -> TradeProposal:
    terms = JudgeTerms(
        judge_summary="Limited evidence: review both arguments and live price before approving a paper trade.",
        confidence_score=0.35,
        estimated_upside_pct=4.0,
        estimated_downside_pct=2.0,
    )
    try:
        news_text = " | ".join(item.get("title", "") for item in (news or [])[:5]) or "No cached market news."
        prompt = PROMPT.format(symbol=symbol, price=price, bull=bull, bear=bear) + f" Cached Marketaux headlines: {news_text}"
        if lessons:
            prompt += f" Similar historical losses: {json.dumps(lessons)}. Lower confidence and explain why this setup may repeat those losses."
        try:
            output = gemini_complete(prompt, temperature=0.1, json_mode=True)
        except Exception:
            output = complete(prompt, temperature=0.1, json_mode=True)
        terms = JudgeTerms.model_validate(json.loads(output))
    except Exception:
        pass
    if lessons:
        terms.confidence_score = min(terms.confidence_score, 0.35)
        terms.judge_summary += " Similar past market setups lost money; review this edge carefully."
    entry = round(price, 2)
    if entry <= 0.01:
        raise ValueError("Latest trade price is too small for a cent-priced bracket")
    stop = round(entry * (1 - terms.estimated_downside_pct / 100), 2)
    target = round(entry * (1 + terms.estimated_upside_pct / 100), 2)
    stop = round(min(entry - 0.01, max(0.01, stop)), 2)
    target = round(max(entry + 0.01, target), 2)
    return TradeProposal(
        symbol=symbol, side="buy", qty=1, target_entry_price=entry,
        stop_loss_price=stop, take_profit_price=target,
        bull_argument=bull, bear_argument=bear,
        judge_summary=terms.judge_summary, confidence_score=terms.confidence_score,
        estimated_upside_pct=terms.estimated_upside_pct,
        estimated_downside_pct=terms.estimated_downside_pct,
    )
