from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda

from intelligence.agents.openrouter_client import complete


PROMPT = PromptTemplate.from_template(
    "You are Coin's bearish risk analyst. Discuss downside and execution risks for {symbol} using only this market data: {market_data}. "
    "State uncertainty and do not invent news, earnings, or financials. Reply in 2-3 sentences."
)


def analyze(symbol: str, market_data: dict) -> str:
    try:
        chain = PROMPT | RunnableLambda(lambda prompt: complete(prompt.to_string()))
        return chain.invoke({"symbol": symbol, "market_data": market_data})
    except Exception:
        return "OpenRouter bear analysis unavailable or rate limited. Price can move through a stop, so realized loss can exceed the planned limit."
