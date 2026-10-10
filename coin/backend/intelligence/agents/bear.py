from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda

from intelligence.agents.openrouter_client import complete
from intelligence.agents.groq_client import complete as groq_complete


PROMPT = PromptTemplate.from_template(
    "You are Coin's bearish risk analyst. Discuss downside and execution risks for {symbol} using only this market data: {market_data}. "
    "State uncertainty and do not invent news, earnings, or financials. Reply in 2-3 sentences."
)


def analyze(symbol: str, market_data: dict) -> str:
    try:
        def generate(prompt):
            try:
                return groq_complete(prompt.to_string())
            except Exception:
                return complete(prompt.to_string())
        chain = PROMPT | RunnableLambda(generate)
        return chain.invoke({"symbol": symbol, "market_data": market_data})
    except Exception:
        return "OpenRouter bear analysis unavailable or rate limited. Price can move through a stop, so realized loss can exceed the planned limit."
