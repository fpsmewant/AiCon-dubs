"""Tests use explicit credentials and mocks, never the developer's local account."""

import pytest


@pytest.fixture(autouse=True)
def isolate_credentials(monkeypatch, tmp_path):
    from db import learning_memory, coinbot_memory
    from intelligence import embeddings
    monkeypatch.setattr(learning_memory, 'PATH', tmp_path / 'learning.sqlite3')
    monkeypatch.setattr(coinbot_memory, 'PATH', tmp_path / 'coinbot.sqlite3')
    monkeypatch.setattr(embeddings, 'PATH', tmp_path / 'vectors.sqlite3')
    for key in ('ALPACA_API_KEY', 'ALPACA_SECRET_KEY', 'GEMINI_API_KEY', 'GEMINI_API_KEY_SECONDARY',
                'GEMINI_API_KEY_TERTIARY',
                'OPENROUTER_API_KEY', 'OPENROUTER_DEBATE_API_KEY',
                'OPENROUTER_GUIDE_API_KEY', 'GROQ_API_KEY', 'MARKETAUX_API_KEY', 'LIQUID_API_KEY'):
        monkeypatch.delenv(key, raising=False)
