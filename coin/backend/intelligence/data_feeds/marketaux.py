"""Marketaux sync with an indexed SQLite cache."""

import os
import re
from threading import Thread
from datetime import datetime, timedelta, timezone

import requests

from db.market_news import finish_sync, latest_sync, list_articles, start_sync, upsert_articles


NEWS_URL = "https://api.marketaux.com/v1/news/all"
CACHE_SECONDS = 300


def normalize_filters(countries: str = "us", symbols: str = "") -> tuple[list[str], list[str]]:
    country_list = sorted({value.strip().lower() for value in countries.split(",") if value.strip()})
    symbol_list = sorted({value.strip().upper() for value in symbols.split(",") if value.strip()})
    if len(country_list) > 8 or any(not re.fullmatch(r"[a-z]{2}", value) for value in country_list):
        raise ValueError("Countries must be up to eight two-letter codes")
    if len(symbol_list) > 12 or any(not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,11}", value) for value in symbol_list):
        raise ValueError("Symbols must be up to twelve valid ticker symbols")
    return country_list, symbol_list


def filter_key(countries: list[str], symbols: list[str]) -> str:
    return f"countries={','.join(countries)}|symbols={','.join(symbols)}"


def cached_news(countries: str = "us", symbols: str = "", limit: int = 20) -> dict:
    country_list, symbol_list = normalize_filters(countries, symbols)
    key = filter_key(country_list, symbol_list)
    last = latest_sync(key)
    return {"articles": list_articles(country_list, symbol_list, limit, last["id"] if last else None),
            "last_sync": last, "new_count": last["new_count"] if last else 0,
            "fetched_count": last["fetched_count"] if last else 0,
            "countries": country_list, "symbols": symbol_list, "cached": True}


def sync_news(countries: str = "us", symbols: str = "", force: bool = False, limit: int = 10) -> dict:
    country_list, symbol_list = normalize_filters(countries, symbols)
    key = filter_key(country_list, symbol_list)
    previous = latest_sync(key)
    if previous and not force:
        finished = datetime.fromisoformat(previous["finished_at"])
        if datetime.now(timezone.utc) - finished < timedelta(seconds=CACHE_SECONDS):
            result = cached_news(countries, symbols, limit)
            result.update({"new_count": 0, "fetched_count": 0, "cache_hit": True})
            return result

    token = os.getenv("MARKETAUX_API_KEY", "").strip()
    if not token:
        raise RuntimeError("MARKETAUX_API_KEY is not configured")
    sync_id, started_at = start_sync(key, country_list, symbol_list)
    params = {"api_token": token, "language": "en", "filter_entities": "true", "limit": min(limit, 10)}
    if country_list:
        params["countries"] = ",".join(country_list)
    if symbol_list:
        params["symbols"] = ",".join(symbol_list)
    if previous:
        after = datetime.fromisoformat(previous["finished_at"]) - timedelta(minutes=5)
        params["published_after"] = after.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        response = requests.get(NEWS_URL, params=params, timeout=(5, 25))
        response.raise_for_status()
        articles = response.json().get("data", [])
        new_count = upsert_articles(sync_id, articles)
        finish_sync(sync_id, len(articles), new_count)
    except Exception:
        finish_sync(sync_id, 0, 0, "failed")
        raise
    result = cached_news(countries, symbols, limit)
    result.update({"new_count": new_count, "fetched_count": len(articles), "cache_hit": False,
                   "sync_started_at": started_at})
    if new_count and os.getenv("LIQUID_EMBEDDING_MODEL"):
        def index_articles():
            try:
                from intelligence.rag import index_market_context
                index_market_context(result["articles"])
            except Exception:
                pass
        Thread(target=index_articles, daemon=True).start()
    return result
