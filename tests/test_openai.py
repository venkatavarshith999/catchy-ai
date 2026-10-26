import json

import httpx
import pytest

from backend.detection import analyze
from llms.product import classify, provider_config


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder-not-a-real-key")
    monkeypatch.delenv("LLM_TIMEOUT", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    # Any test that forgets to mock explicitly must never send network traffic.
    def forbidden(*args, **kwargs):
        raise AssertionError("Unexpected network request")

    monkeypatch.setattr("llms.product.httpx.post", forbidden)


def response(body, status=200):
    return httpx.Response(
        status, request=httpx.Request("POST", "https://api.openai.com/v1/responses"), json=body
    )


def completed(signals):
    return {
        "status": "completed",
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": json.dumps({"signals": signals})}],
            }
        ],
    }


def test_request_redacts_bounds_context_and_keeps_key_server_side(monkeypatch):
    captured = []

    def answer(url, **kwargs):
        captured.append((url, kwargs))
        return response(completed([]))

    monkeypatch.setattr("llms.product.httpx.post", answer)
    turns = ["Earlier conversation"] * 10 + ["My number is 9876543210"]
    result = classify(turns, "te")
    assert result["model_status"] == "connected"
    url, request = captured[0]
    assert url == "https://api.openai.com/v1/responses"
    assert request["headers"]["Authorization"].startswith("Bearer test-")
    payload = request["json"]
    assert "9876543210" not in json.dumps(payload)
    assert "test-placeholder" not in json.dumps(payload)
    assert "te" in payload["instructions"]
    context = json.loads(payload["input"][0]["content"])
    assert len(context) == 8 and context[0]["turn"] == 4 and context[-1]["turn"] == 11
    assert payload["store"] is False and payload["max_output_tokens"] == 1600
    assert payload["text"]["format"]["strict"] is True
    assert request["follow_redirects"] is False and request["timeout"] == 5
    assert "test-placeholder" not in json.dumps(result)


@pytest.mark.parametrize(
    "failure", ["timeout", "auth", "quota", "incomplete", "refusal", "invalid"]
)
def test_failure_preserves_rule_evidence(monkeypatch, failure):
    def answer(*args, **kwargs):
        if failure == "timeout":
            raise httpx.ReadTimeout("sensitive provider details")
        if failure in {"auth", "quota"}:
            return response(
                {"error": "sensitive provider details"}, 401 if failure == "auth" else 429
            )
        if failure == "incomplete":
            return response({**completed([]), "status": "incomplete"})
        if failure == "refusal":
            return response(
                {
                    "status": "completed",
                    "output": [
                        {"type": "message", "content": [{"type": "refusal", "refusal": "no"}]}
                    ],
                }
            )
        return response({"status": "completed", "output": []})

    monkeypatch.setattr("llms.product.httpx.post", answer)
    turns = ["Read your OTP to me"]
    expected = analyze(turns, "en")
    result = classify(turns, "en")
    assert result["model_status"] == "unavailable"
    assert result["score"] == expected["score"] and result["signals"] == expected["signals"]
    assert "sensitive" not in json.dumps(result)


def test_missing_key_never_calls_provider(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY")
    called = []
    monkeypatch.setattr("llms.product.httpx.post", lambda *a, **k: called.append(True))
    assert provider_config() == {"provider": "openai", "configured": False}
    assert classify(["Hello there"], "en")["model_status"] == "unavailable"
    assert not called


def test_evidence_cannot_be_invented_or_advice_promoted(monkeypatch):
    text = "Never share your OTP with anyone"
    signals = [
        {"key": "credential", "turn": 1, "quote": text},
        {"key": "remote", "turn": 1, "quote": "Install remote access now"},
        {"key": "fear", "turn": 999, "quote": text},
    ]
    monkeypatch.setattr("llms.product.httpx.post", lambda *a, **k: response(completed(signals)))
    assert classify([text], "en")["level"] == "low"


def test_model_cannot_clear_rule_findings(monkeypatch):
    monkeypatch.setattr("llms.product.httpx.post", lambda *a, **k: response(completed([])))
    result = classify(["Read your OTP to me"], "en")
    assert result["level"] == "high" and result["model_status"] == "connected"


def test_model_can_add_valid_context(monkeypatch):
    text = "Keep this conversation between us"
    signals = [{"key": "secrecy", "turn": 1, "quote": text}]
    monkeypatch.setattr("llms.product.httpx.post", lambda *a, **k: response(completed(signals)))
    result = classify([text], "en")
    assert result["model_status"] == "connected"
    assert any(s["key"] == "secrecy" and s["quote"] == text for s in result["signals"])
