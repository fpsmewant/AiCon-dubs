"""Incremental embedding backfill. Run from backend: python -m intelligence.index_memory."""

import json

from db.market_news import connection as news_connection
from db.learning_memory import connection as learning_connection
from intelligence.embeddings import store_document, search
from intelligence.rag import index_market_context

TICKER_NOTES = {
    'NVDA': 'Nvidia (NVDA) is a US-listed semiconductor company associated with GPUs, accelerated computing, artificial intelligence and data centers.',
    'AAPL': 'Apple (AAPL) is a US-listed technology company associated with iPhone, consumer devices and software services.',
    'MSFT': 'Microsoft (MSFT) is a US-listed technology company associated with enterprise software, Azure cloud and artificial intelligence.',
    'AMZN': 'Amazon (AMZN) is a US-listed company associated with e-commerce and AWS cloud infrastructure.',
    'TSLA': 'Tesla (TSLA) is a US-listed company associated with electric vehicles and energy storage.',
    'SPY': 'SPY is a US-listed ETF tracking the S&P 500 US large-cap stock index.',
    'QQQ': 'QQQ is a US-listed ETF tracking the Nasdaq-100 index with substantial technology exposure.',
}


def index_database() -> dict:
    count = 0
    for symbol, note in TICKER_NOTES.items():
        store_document('ticker_description', note, symbol, f'ticker:{symbol}')
        count += 1
    with news_connection() as db:
        articles = [json.loads(row['raw_json']) for row in db.execute('SELECT raw_json FROM articles ORDER BY published_at DESC')]
    for article in articles:
        normalized = article | {'symbols': [e.get('symbol', '') for e in article.get('entities', [])]}
        index_market_context([normalized])
        count += 1
    index_trade_outcomes()
    return {'indexed_documents': count}


def index_trade_outcomes() -> None:
    with learning_connection() as db:
        rows = [dict(row) for row in db.execute("SELECT * FROM trades WHERE outcome IS NOT NULL")]
    for row in rows:
        summary = (f"{row['symbol']} {row['side']} trade at {row['submitted_at']} had {row['outcome']} "
                   f"outcome with return {row['return_pct']:.2f} percent. Pre-trade conditions: {row['pre_snapshot']}.")
        store_document('trade_memory', summary, row['symbol'], f"trade:{row['order_id']}")


if __name__ == '__main__':
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    result = index_database()
    result['tech_retrieval'] = [{'symbol': item['symbol'], 'score': item['score']}
                              for item in search('US technology stocks Nvidia AI GPUs data centers', 3)]
    print(result)
