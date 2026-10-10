"""Minimal Gemini REST client for Coin's evidence synthesis."""

import json
import os

import requests


BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def complete(prompt: str, *, json_mode: bool = False, temperature: float = 0.15,
             prefer_secondary: bool = False, prefer_tertiary: bool = False) -> str:
    keys = [value for value in (os.getenv("GEMINI_API_KEY", "").strip(),
                                os.getenv("GEMINI_API_KEY_SECONDARY", "").strip(),
                                os.getenv("GEMINI_API_KEY_TERTIARY", "").strip()) if value]
    keys = list(dict.fromkeys(keys))
    preferred = (os.getenv("GEMINI_API_KEY_TERTIARY", "").strip() if prefer_tertiary else
                 os.getenv("GEMINI_API_KEY_SECONDARY", "").strip() if prefer_secondary else "")
    if preferred in keys:
        index = keys.index(preferred)
        keys = keys[index:] + keys[:index]
    if not keys:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    generation = {"temperature": temperature, "maxOutputTokens": 1200}
    if json_mode:
        generation["responseMimeType"] = "application/json"
    last_error = None
    for key in keys:
        try:
            response = requests.post(
                f"{BASE_URL}/{model}:generateContent",
                headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": generation},
                timeout=(5, 35),
            )
            response.raise_for_status()
            break
        except requests.RequestException as exc:
            last_error = exc
    else:
        raise last_error
    parts = response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts).strip()
    if not text:
        raise ValueError("Gemini returned no text")
    if json_mode:
        json.loads(text)
    return text
