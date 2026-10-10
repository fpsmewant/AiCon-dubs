"""Groq chat client for the bearish analyst."""

import os
import requests


def complete(prompt: str) -> str:
    key = os.getenv('GROQ_API_KEY', '').strip()
    if not key:
        raise RuntimeError('GROQ_API_KEY is not configured')
    response = requests.post('https://api.groq.com/openai/v1/chat/completions',
                             headers={'Authorization': f'Bearer {key}'},
                             json={'model': os.getenv('GROQ_BEAR_MODEL', 'openai/gpt-oss-20b'),
                                   'messages': [{'role': 'user', 'content': prompt}],
                                   'temperature': 0.15, 'max_tokens': 500}, timeout=(5, 25))
    response.raise_for_status()
    text = response.json()['choices'][0]['message']['content']
    if not isinstance(text, str) or not text.strip():
        raise ValueError('Groq returned no analyst text')
    return text.strip()
