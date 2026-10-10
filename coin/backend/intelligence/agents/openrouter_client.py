"""Small OpenRouter chat client shared by the debate roles."""

import os

import requests


CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"


def complete(
    prompt: str,
    *,
    temperature: float = 0.2,
    json_mode: bool = False,
    model: str | None = None,
    key_env: str = "OPENROUTER_DEBATE_API_KEY",
) -> str:
    key = os.getenv(key_env, "").strip() or os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")

    payload = {
        "model": model or os.getenv("OPENROUTER_DEBATE_MODEL") or os.getenv("OPENROUTER_MODEL", "dots-studio/dots-3-note-preview:free"),
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": 1200,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    response = requests.post(
        CHAT_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload,
        timeout=(10, 30),
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]

    if not isinstance(content, str) or not content.strip():
        raise ValueError("OpenRouter returned no text")
    return content.strip()
