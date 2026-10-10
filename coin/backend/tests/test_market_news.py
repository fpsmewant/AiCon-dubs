from db import market_news
from intelligence.data_feeds import marketaux


def article(article_id="story-1"):
    return {
        "uuid": article_id,
        "title": "A measured market headline",
        "description": "Description",
        "snippet": "Snippet",
        "url": f"https://example.com/{article_id}",
        "source": "example.com",
        "language": "en",
        "published_at": "2026-10-10T10:00:00Z",
        "entities": [{"symbol": "AAPL", "country": "us", "sentiment_score": 0.2}],
    }


def test_sqlite_deduplicates_and_tracks_new_since_latest_sync(tmp_path, monkeypatch):
    monkeypatch.setattr(market_news, "PATH", tmp_path / "news.sqlite3")
    market_news.initialize()
    first, _ = market_news.start_sync("test", ["us"], ["AAPL"])
    assert market_news.upsert_articles(first, [article()]) == 1
    market_news.finish_sync(first, 1, 1)
    assert market_news.list_articles(["us"], ["AAPL"], current_sync_id=first)[0]["is_new"] is True
    second, _ = market_news.start_sync("test", ["us"], ["AAPL"])
    assert market_news.upsert_articles(second, [article()]) == 0
    market_news.finish_sync(second, 1, 0)
    stored = market_news.list_articles(["us"], ["AAPL"], current_sync_id=second)
    assert len(stored) == 1
    assert stored[0]["is_new"] is False


def test_recent_sync_uses_database_without_network(monkeypatch):
    monkeypatch.setattr(marketaux, "latest_sync", lambda key: {
        "id": 3, "finished_at": "2999-01-01T00:00:00+00:00", "new_count": 0, "fetched_count": 2,
    })
    monkeypatch.setattr(marketaux, "cached_news", lambda *args, **kwargs: {"articles": [article()]})
    monkeypatch.setattr(marketaux.requests, "get", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network called")))
    result = marketaux.sync_news("us", "AAPL")
    assert result["cache_hit"] is True
    assert len(result["articles"]) == 1
