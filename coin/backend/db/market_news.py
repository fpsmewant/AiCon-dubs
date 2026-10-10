"""Indexed SQLite cache for Marketaux articles and sync history."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


PATH = Path(__file__).with_name("market_news.sqlite3")


@contextmanager
def connection():
    database = sqlite3.connect(PATH, timeout=5)
    database.row_factory = sqlite3.Row
    database.execute("PRAGMA journal_mode=WAL")
    database.execute("PRAGMA synchronous=NORMAL")
    try:
        yield database
        database.commit()
    finally:
        database.close()


def initialize() -> None:
    with connection() as database:
        database.executescript("""
            CREATE TABLE IF NOT EXISTS sync_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filter_key TEXT NOT NULL,
                countries TEXT NOT NULL,
                symbols TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                fetched_count INTEGER NOT NULL DEFAULT 0,
                new_count INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'running'
            );
            CREATE INDEX IF NOT EXISTS idx_sync_filter_finished
                ON sync_runs(filter_key, finished_at DESC);
            CREATE TABLE IF NOT EXISTS articles (
                uuid TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                snippet TEXT,
                url TEXT NOT NULL,
                image_url TEXT,
                source TEXT,
                language TEXT,
                published_at TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                first_seen_sync_id INTEGER,
                last_seen_sync_id INTEGER,
                raw_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at DESC);
            CREATE INDEX IF NOT EXISTS idx_articles_last_seen ON articles(last_seen_at DESC);
            CREATE TABLE IF NOT EXISTS article_entities (
                article_uuid TEXT NOT NULL,
                symbol TEXT NOT NULL,
                country TEXT,
                name TEXT,
                industry TEXT,
                match_score REAL,
                sentiment_score REAL,
                PRIMARY KEY(article_uuid, symbol),
                FOREIGN KEY(article_uuid) REFERENCES articles(uuid) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_entities_symbol ON article_entities(symbol, article_uuid);
            CREATE INDEX IF NOT EXISTS idx_entities_country ON article_entities(country, article_uuid);
        """)


def start_sync(filter_key: str, countries: list[str], symbols: list[str]) -> tuple[int, str]:
    started_at = datetime.now(timezone.utc).isoformat()
    with connection() as database:
        cursor = database.execute(
            "INSERT INTO sync_runs(filter_key,countries,symbols,started_at) VALUES(?,?,?,?)",
            (filter_key, ",".join(countries), ",".join(symbols), started_at),
        )
        return int(cursor.lastrowid), started_at


def finish_sync(sync_id: int, fetched: int, new: int, status: str = "complete") -> None:
    with connection() as database:
        database.execute(
            "UPDATE sync_runs SET finished_at=?, fetched_count=?, new_count=?, status=? WHERE id=?",
            (datetime.now(timezone.utc).isoformat(), fetched, new, status, sync_id),
        )


def latest_sync(filter_key: str) -> dict | None:
    with connection() as database:
        row = database.execute(
            "SELECT * FROM sync_runs WHERE filter_key=? AND status='complete' ORDER BY finished_at DESC LIMIT 1",
            (filter_key,),
        ).fetchone()
    return dict(row) if row else None


def upsert_articles(sync_id: int, articles: list[dict]) -> int:
    now = datetime.now(timezone.utc).isoformat()
    new_count = 0
    with connection() as database:
        for article in articles:
            article_id = article.get("uuid")
            if not article_id or not article.get("title") or not article.get("url") or not article.get("published_at"):
                continue
            exists = database.execute("SELECT 1 FROM articles WHERE uuid=?", (article_id,)).fetchone()
            if not exists:
                new_count += 1
            database.execute("""
                INSERT INTO articles(uuid,title,description,snippet,url,image_url,source,language,published_at,
                    first_seen_at,last_seen_at,first_seen_sync_id,last_seen_sync_id,raw_json)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(uuid) DO UPDATE SET
                    title=excluded.title, description=excluded.description, snippet=excluded.snippet,
                    url=excluded.url, image_url=excluded.image_url, source=excluded.source,
                    last_seen_at=excluded.last_seen_at, last_seen_sync_id=excluded.last_seen_sync_id,
                    raw_json=excluded.raw_json
            """, (
                article_id, article["title"], article.get("description"), article.get("snippet"),
                article["url"], article.get("image_url"), article.get("source"), article.get("language"),
                article["published_at"], now, now, sync_id, sync_id, json.dumps(article),
            ))
            for entity in article.get("entities") or []:
                symbol = (entity.get("symbol") or "").upper()
                if not symbol:
                    continue
                database.execute("""
                    INSERT INTO article_entities(article_uuid,symbol,country,name,industry,match_score,sentiment_score)
                    VALUES(?,?,?,?,?,?,?)
                    ON CONFLICT(article_uuid,symbol) DO UPDATE SET
                        country=excluded.country, name=excluded.name, industry=excluded.industry,
                        match_score=excluded.match_score, sentiment_score=excluded.sentiment_score
                """, (article_id, symbol, entity.get("country"), entity.get("name"), entity.get("industry"),
                      entity.get("match_score"), entity.get("sentiment_score")))
    return new_count


def list_articles(countries: list[str], symbols: list[str], limit: int = 20, current_sync_id: int | None = None) -> list[dict]:
    clauses, params = [], []
    if countries:
        clauses.append("e.country IN (%s)" % ",".join("?" * len(countries)))
        params.extend(countries)
    if symbols:
        clauses.append("e.symbol IN (%s)" % ",".join("?" * len(symbols)))
        params.extend(symbols)
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    query = f"""
        SELECT a.*, GROUP_CONCAT(DISTINCT e.symbol) AS symbols,
               AVG(e.sentiment_score) AS sentiment_score
        FROM articles a LEFT JOIN article_entities e ON e.article_uuid=a.uuid
        {where}
        GROUP BY a.uuid ORDER BY a.published_at DESC LIMIT ?
    """
    params.append(min(max(limit, 1), 50))
    with connection() as database:
        rows = database.execute(query, params).fetchall()
    return [{
        "uuid": row["uuid"], "title": row["title"], "description": row["description"],
        "snippet": row["snippet"], "url": row["url"], "image_url": row["image_url"],
        "source": row["source"], "published_at": row["published_at"],
        "first_seen_at": row["first_seen_at"], "last_seen_at": row["last_seen_at"],
        "is_new": current_sync_id is not None and row["first_seen_sync_id"] == current_sync_id,
        "symbols": row["symbols"].split(",") if row["symbols"] else [],
        "sentiment_score": round(row["sentiment_score"], 4) if row["sentiment_score"] is not None else None,
    } for row in rows]


initialize()
