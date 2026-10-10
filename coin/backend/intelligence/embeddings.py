"""OpenRouter-compatible Liquid embedding client and indexed SQLite vector memory."""

import hashlib
import json
import math
import os
import sqlite3
import struct
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

import requests

PATH = Path(__file__).resolve().parents[1] / "db" / "memory.sqlite3"
EMBEDDINGS_URL = "https://openrouter.ai/api/v1/embeddings"


def embed(text: str) -> list[float]:
    key = os.getenv("LIQUID_API_KEY", "").strip()
    model = os.getenv("LIQUID_EMBEDDING_MODEL", "").strip()
    if not key or not model:
        raise RuntimeError("LIQUID_API_KEY and LIQUID_EMBEDDING_MODEL must be configured")
    response = requests.post(
        os.getenv("LIQUID_EMBEDDING_URL", EMBEDDINGS_URL),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": model, "input": text[:1400]}, timeout=(5, 20),
    )
    response.raise_for_status()
    vector = response.json()["data"][0]["embedding"]
    if not vector or not all(isinstance(value, (float, int)) and math.isfinite(value) for value in vector):
        raise ValueError("Embedding provider returned an invalid vector")
    return [float(value) for value in vector]


@contextmanager
def connection():
    PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(PATH, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS documents (
        id TEXT PRIMARY KEY, kind TEXT NOT NULL, symbol TEXT, text TEXT NOT NULL,
        vector TEXT NOT NULL, model TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_documents_kind_symbol ON documents(kind, symbol)")
    try:
        yield db
        db.commit()
    finally:
        db.close()


def store_document(kind: str, text: str, symbol: str = "", document_id: str = "") -> str:
    document_id = document_id or hashlib.sha256(f"{kind}:{symbol}:{text}".encode()).hexdigest()
    model = os.getenv("LIQUID_EMBEDDING_MODEL", "")
    with connection() as db:
        existing = db.execute("SELECT model,text,vector FROM documents WHERE id=?", (document_id,)).fetchone()
        if existing and existing["model"] == model and existing['text'] == text:
            if isinstance(existing['vector'], str):
                previous = json.loads(existing['vector'])
                db.execute('UPDATE documents SET vector=? WHERE id=?',
                           (struct.pack(f'<{len(previous)}f', *previous), document_id))
            return document_id
    vector = embed(text)
    with connection() as db:
        db.execute("""INSERT INTO documents(id,kind,symbol,text,vector,model) VALUES(?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET text=excluded.text,vector=excluded.vector,
            model=excluded.model,updated_at=CURRENT_TIMESTAMP""",
            (document_id, kind, symbol.upper(), text, struct.pack(f'<{len(vector)}f', *vector), model))
    return document_id


@lru_cache(maxsize=256)
def _query_vector(model: str, url: str, query: str) -> tuple[float, ...]:
    return tuple(embed(query))


def search(query: str, limit: int = 5, kind: str | None = None) -> list[dict]:
    query_vector = _query_vector(os.getenv('LIQUID_EMBEDDING_MODEL', ''),
                                 os.getenv('LIQUID_EMBEDDING_URL', EMBEDDINGS_URL), query.strip())
    with connection() as db:
        rows = db.execute("SELECT * FROM documents WHERE model=? AND (? IS NULL OR kind=?)",
                          (os.getenv("LIQUID_EMBEDDING_MODEL", ""), kind, kind)).fetchall()
    length = math.sqrt(sum(value * value for value in query_vector))
    matches = []
    for row in rows:
        stored = row['vector']
        vector = struct.unpack(f'<{len(stored) // 4}f', stored) if isinstance(stored, bytes) else json.loads(stored)
        if len(vector) != len(query_vector):
            continue
        norm = math.sqrt(sum(value * value for value in vector)) * length
        score = sum(a * b for a, b in zip(vector, query_vector)) / norm if norm else 0
        matches.append({"id": row["id"], "kind": row["kind"], "symbol": row["symbol"],
                        "text": row["text"], "score": round(score, 4)})
    return sorted(matches, key=lambda item: item["score"], reverse=True)[:limit]
