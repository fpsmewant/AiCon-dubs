"""Minimal Gemini REST client for Coin's evidence synthesis."""

import json
import os

import requests


BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def complete(prompt: str, *, json_mode: bool = False, temperature: float = 0.15) -> str:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    generation = {"temperature": temperature, "maxOutputTokens": 1200}
    if json_mode:
        generation["responseMimeType"] = "application/json"
    response = requests.post(
        f"{BASE_URL}/{model}:generateContent",
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": generation},
        timeout=(10, 45),
    )
    response.raise_for_status()
    parts = response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts).strip()
    if not text:
        raise ValueError("Gemini returned no text")
    if json_mode:
        json.loads(text)
    return text
