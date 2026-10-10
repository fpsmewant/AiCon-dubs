import json

from intelligence.agents import gemini_client


def test_gemini_client_uses_header_and_json_mode(monkeypatch):
    sent = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": '{"result":"ok"}'}]}}]}

    def post(url, *, headers, json, timeout):
        sent.update(url=url, headers=headers, payload=json, timeout=timeout)
        return Response()

    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")
    monkeypatch.setattr(gemini_client.requests, "post", post)
    assert json.loads(gemini_client.complete("prompt", json_mode=True))["result"] == "ok"
    assert sent["headers"]["x-goog-api-key"] == "test-gemini"
    assert sent["url"].endswith("/gemini-test:generateContent")
    assert sent["payload"]["generationConfig"]["responseMimeType"] == "application/json"
