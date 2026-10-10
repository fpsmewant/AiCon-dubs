import json

from intelligence.voice import guide, transcription


def candidate(symbol="SPY"):
    return {
        "symbol": symbol,
        "price": 100,
        "return_20d_pct": 3.2,
        "average_daily_range_pct": 1.1,
        "shares": 1,
        "estimated_cost": 100,
    }


def test_irrelevant_prompt_is_rejected_without_model_call(monkeypatch):
    monkeypatch.setattr(guide, "complete", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()))
    plan = guide.build_guide("What is C++?", [candidate()], {"SPY": []})
    assert plan.valid is False
    assert plan.steps == []


def test_guide_filters_unknown_symbols_and_steps(monkeypatch):
    monkeypatch.setattr(guide, "complete", lambda *args, **kwargs: json.dumps({
        "valid": True,
        "spoken_summary": "Let's compare the visible evidence.",
        "horizon": "long_term",
        "budget": 100,
        "symbols": ["SPY", "FAKE"],
        "steps": ["opportunities", "outside"],
        "key_points": ["SPY is the available comparison."],
    }))
    plan = guide.build_guide("Where could I invest $100 long term?", [candidate()], {"SPY": []})
    assert plan.symbols == ["SPY"]
    assert plan.steps == ["opportunities"]
    assert plan.budget == 100
    assert plan.allocations[0]["amount"] == 100
    assert plan.allocations[0]["fractional_shares_reference"] == 1


def test_transcription_sends_audio_to_groq_whisper(monkeypatch):
    sent = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"text": "invest one hundred dollars"}

    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    monkeypatch.setattr(transcription.requests, "post", lambda url, **kwargs: sent.update(url=url, **kwargs) or Response())
    assert transcription.transcribe_audio("question.webm", "audio/webm;codecs=opus", b"audio") == "invest one hundred dollars"
    assert sent["data"]["model"] == "whisper-large-v3-turbo"
    assert sent["headers"]["Authorization"] == "Bearer test-groq"
