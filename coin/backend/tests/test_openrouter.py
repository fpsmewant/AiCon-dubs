import json

from intelligence.agents import bear, bull, judge, openrouter_client


def test_openrouter_client_uses_one_configured_key_and_json_mode(monkeypatch):
    sent = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": '{"judge_summary":"Cautious"}'}}]}

    def post(url, *, headers, json, timeout):
        sent.update(url=url, headers=headers, payload=json, timeout=timeout)
        return Response()

    monkeypatch.setenv("OPENROUTER_DEBATE_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_DEBATE_MODEL", "openrouter/free")
    monkeypatch.setattr(openrouter_client.requests, "post", post)
    assert json.loads(openrouter_client.complete("judge prompt", json_mode=True))["judge_summary"] == "Cautious"
    assert sent["url"] == openrouter_client.CHAT_URL
    assert sent["headers"]["Authorization"] == "Bearer test-key"
    assert sent["payload"]["model"] == "openrouter/free"
    assert sent["payload"]["response_format"] == {"type": "json_object"}


def test_analysis_roles_fall_back_when_openrouter_is_missing(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_DEBATE_API_KEY", raising=False)
    assert "OpenRouter" in bull.analyze("AAPL", {"latest_trade_price": 100})
    assert "OpenRouter" in bear.analyze("AAPL", {"latest_trade_price": 100})
    proposal = judge.propose("AAPL", 100, "Bull case", "Bear case")
    assert proposal.confidence_score == 0.35


def test_judge_accepts_schema_checked_openrouter_response(monkeypatch):
    monkeypatch.setattr(judge, "gemini_complete", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError()))
    monkeypatch.setattr(judge, "complete", lambda *args, **kwargs: json.dumps({
        "judge_summary": "Small test trade.",
        "confidence_score": 0.52,
        "estimated_upside_pct": 3,
        "estimated_downside_pct": 1,
    }))
    proposal = judge.propose("AAPL", 100, "Bull case", "Bear case")
    assert proposal.judge_summary == "Small test trade."
    assert proposal.stop_loss_price == 99
    assert proposal.take_profit_price == 103
