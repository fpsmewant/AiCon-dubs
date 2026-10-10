"""Best effort retrieval: provider failure never fabricates market context."""

from intelligence.embeddings import search, store_document


def index_market_context(news: list[dict], notes: list[str] | None = None) -> None:
    for article in news:
        text = f"{article.get('published_at', '')} {article.get('title', '')}. {article.get('description') or article.get('snippet') or ''}"
        for symbol in article.get("symbols") or [""]:
            store_document("news", text, symbol, article.get("uuid", "") + ":" + symbol)
    for note in notes or []:
        store_document("market_note", note)


def relevant_context(query: str, limit: int = 5) -> list[dict]:
    try:
        return [item for item in search(query, limit) if item["score"] > 0.2]
    except (RuntimeError, ValueError, OSError, KeyError):
        return []
