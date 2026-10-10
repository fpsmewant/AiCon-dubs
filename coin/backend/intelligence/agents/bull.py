from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda

from intelligence.agents.openrouter_client import complete
from intelligence.agents.gemini_client import complete as gemini_complete


PROMPT = PromptTemplate.from_template(
    "You are Coin's bullish stock analyst. Discuss the upside case for {symbol} using only this market data: {market_data}. "
    "State uncertainty and do not invent news, earnings, or financials. Reply in 2-3 sentences."
)


def analyze(symbol: str, market_data: dict) -> str:
    try:
        def generate(prompt):
            try:
                return gemini_complete(prompt.to_string(), prefer_secondary=True)
            except Exception:
                return complete(prompt.to_string())
        chain = PROMPT | RunnableLambda(generate)
        return chain.invoke({"symbol": symbol, "market_data": market_data})
    except Exception:
        return "OpenRouter bull analysis unavailable or rate limited. A recent trade price exists, but no upside catalyst was verified."
