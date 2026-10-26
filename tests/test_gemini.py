import json

import httpx
import pytest

from backend.detection import analyze
from llms.product import classify, provider_config


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-placeholder-not-a-real-key")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("LLM_TIMEOUT", raising=False)
    monkeypatch.setattr(
        "llms.product.httpx.post", lambda *a, **k: pytest.fail("Unexpected network")
    )


def response(body, status=200):
    return httpx.Response(
        status,
        request=httpx.Request("POST", "https://generativelanguage.googleapis.com"),
        json=body,
    )


def completed(signals):
    return {
        "candidates": [
            {
                "finishReason": "STOP",
                "content": {"parts": [{"text": json.dumps({"signals": signals})}]},
            }
        ]
    }


def test_gemini_request_redacts_bounds_and_authenticates_in_header(monkeypatch):
    captured = []

    def answer(url, **kwargs):
        captured.append((url, kwargs))
        return response(completed([]))

    monkeypatch.setattr("llms.product.httpx.post", answer)
    result = classify(["Earlier conversation"] * 10 + ["My number is 9876543210"], "hi")
    assert result["model_status"] == "connected"
    url, request = captured[0]
    assert (
        url
        == "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent"
    )
    assert "test-placeholder" not in url
    assert request["headers"]["x-goog-api-key"] == "test-placeholder-not-a-real-key"
    payload = request["json"]
    assert "9876543210" not in json.dumps(payload)
    assert "test-placeholder" not in json.dumps(payload)
    turns = json.loads(payload["contents"][0]["parts"][0]["text"])
    assert len(turns) == 8 and turns[0]["turn"] == 4 and turns[-1]["turn"] == 11
    assert payload["generationConfig"]["responseJsonSchema"]["additionalProperties"] is False
    assert request["timeout"] == 5 and request["follow_redirects"] is False


@pytest.mark.parametrize(
    "failure", ["auth", "quota", "timeout", "blocked", "truncated", "empty", "malformed"]
)
def test_gemini_failure_preserves_rules(monkeypatch, failure):
    def answer(*a, **k):
        if failure == "timeout":
            raise httpx.ReadTimeout("private details")
        if failure in {"auth", "quota"}:
            return response({"error": "private details"}, 403 if failure == "auth" else 429)
        if failure == "blocked":
            return response({"promptFeedback": {"blockReason": "SAFETY"}})
        if failure == "empty":
            return response({"candidates": []})
        data = completed([])
        if failure == "truncated":
            data["candidates"][0]["finishReason"] = "MAX_TOKENS"
        else:
            data["candidates"][0]["content"]["parts"][0]["text"] = "not JSON"
        return response(data)

    monkeypatch.setattr("llms.product.httpx.post", answer)
    turns = ["Read your OTP to me"]
    result, expected = classify(turns, "en"), analyze(turns, "en")
    assert result["model_status"] == "unavailable"
    assert result["score"] == expected["score"] and result["signals"] == expected["signals"]
    assert "private details" not in json.dumps(result)


def test_gemini_missing_key_and_invalid_model_make_no_request(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY")
    assert provider_config() == {"provider": "gemini", "configured": False}
    assert classify(["Hello"], "en")["model_status"] == "unavailable"
    monkeypatch.setenv("GEMINI_API_KEY", "test-placeholder")
    monkeypatch.setenv("GEMINI_MODEL", "../../other?key=bad")
    assert classify(["Hello"], "en")["model_status"] == "unavailable"


def test_gemini_valid_evidence_and_invented_evidence(monkeypatch):
    text = "Keep this conversation between us"
    signals = [
        {"key": "secrecy", "turn": 1, "quote": text},
        {"key": "credential", "turn": 1, "quote": "Read your OTP to me"},
    ]
    monkeypatch.setattr("llms.product.httpx.post", lambda *a, **k: response(completed(signals)))
    result = classify([text], "en")
    assert result["model_status"] == "connected"
    assert "secrecy" in {s["key"] for s in result["signals"]}
    assert "credential" not in {s["key"] for s in result["signals"]}
