"""Groq Whisper speech-to-text adapter."""

import os

import requests


TRANSCRIPTION_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
SUPPORTED_AUDIO_TYPES = {
    "audio/webm", "audio/ogg", "audio/wav", "audio/x-wav", "audio/mpeg",
    "audio/mp4", "audio/m4a", "video/webm",
}


def transcribe_audio(filename: str, content_type: str, audio: bytes) -> str:
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GROQ_API_KEY is not configured")
    if not audio:
        raise ValueError("The recording was empty")
    if len(audio) > 10 * 1024 * 1024:
        raise ValueError("The recording is larger than 10 MB")
    normalized_type = content_type.split(";", 1)[0].lower()
    if normalized_type not in SUPPORTED_AUDIO_TYPES:
        raise ValueError("Unsupported audio format")

    response = requests.post(
        TRANSCRIPTION_URL,
        headers={"Authorization": f"Bearer {key}"},
        files={"file": (filename or "question.webm", audio, normalized_type)},
        data={
            "model": os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo"),
            "language": "en",
            "response_format": "json",
            "temperature": "0",
            "prompt": "Coin paper trading guide. Stock symbols, dollars, short term, long term, risk and investing.",
        },
        timeout=(10, 45),
    )
    response.raise_for_status()
    text = response.json().get("text", "").strip()
    if not text:
        raise ValueError("No speech was detected")
    return text
