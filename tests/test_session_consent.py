"""Authorization and withdrawal boundaries without contacting speech/model providers."""

import asyncio
import json
import time

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.detection import analyze, redact
from backend.product import create_app
from backend.product_store import Call

ORIGIN = "http://localhost:8000"
HEADERS = {"Origin": ORIGIN, "X-Catchy-Request": "1"}


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("APP_ORIGIN", ORIGIN)
    monkeypatch.setenv("LLM_PROVIDER", "rules")
    monkeypatch.setenv("ASR_WS_URL", "ws://speech.invalid")
    monkeypatch.setenv("ASR_SERVICE_TOKEN", "")
    monkeypatch.setenv("ERROR_WEBHOOK_URL", "")
    return create_app("sqlite:///" + str(tmp_path / "consent.db"), redis_url="")


@pytest.fixture
def client(app):
    with TestClient(app, headers=HEADERS) as client:
        yield client


def register(client, email="owner@example.test"):
    response = client.post(
        "/api/v2/auth/register",
        json={"name": "Test Owner", "email": email, "password": "test-password-123"},
    )
    assert response.status_code == 200


def new_call(client, mode="speaker", language="en"):
    response = client.post(
        "/api/v2/calls",
        json={"title": "Speech test", "mode": mode, "language": language, "consent": True},
    )
    assert response.status_code == 201
    return response.json()["id"]


def asr_url(cid, language="en-IN"):
    return f"/api/v2/asr?call_id={cid}&language={language}"


class FakeSpeech:
    def __init__(self):
        self.messages = asyncio.Queue()
        self.sent = []
        self.connections = []
        self.closed = False

    def connect(self, *args, **kwargs):
        self.connections.append((args, kwargs))
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        self.closed = True

    async def send(self, value):
        self.sent.append(value)
        if isinstance(value, bytes):
            await self.messages.put(json.dumps({"text": "Read OTP 123456 to me"}))

    def __aiter__(self):
        return self

    async def __anext__(self):
        return await self.messages.get()


@pytest.fixture
def speech(monkeypatch):
    speech = FakeSpeech()
    monkeypatch.setattr("websockets.connect", speech.connect)
    return speech


@pytest.mark.parametrize(
    "denial",
    [
        "missing_call",
        "unknown_call",
        "other_owner",
        "completed",
        "withdrawn",
        "deleted",
        "expired",
        "typed_mode",
        "context_expired",
        "wrong_language",
        "missing_language",
        "signed_out",
        "wrong_origin",
    ],
)
def test_asr_denies_before_provider_connection(app, client, speech, denial):
    register(client)
    cid = new_call(client, mode="typed" if denial == "typed_mode" else "speaker")
    url, headers = asr_url(cid), {"Origin": ORIGIN}
    if denial == "missing_call":
        url = "/api/v2/asr?language=en-IN"
    elif denial == "unknown_call":
        url = asr_url("missing-session")
    elif denial == "other_owner":
        register(client, "other@example.test")
    elif denial in {"completed", "withdrawn", "expired"}:
        with app.state.Session.begin() as db:
            call = db.get(Call, cid)
            if denial == "expired":
                call.expires = time.time() - 1
            else:
                call.status = denial
    elif denial == "deleted":
        assert client.delete(f"/api/v2/calls/{cid}").status_code == 200
    elif denial == "context_expired":
        app.state.live.delete("call:" + cid)
    elif denial == "wrong_language":
        url = asr_url(cid, "te-IN")
    elif denial == "missing_language":
        url = f"/api/v2/asr?call_id={cid}"
    elif denial == "signed_out":
        client.cookies.clear()
    elif denial == "wrong_origin":
        headers = {"Origin": "https://other.invalid"}
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect(url, headers=headers):
            pytest.fail("A denied session must not accept a websocket")
    assert error.value.code == 1008
    assert speech.connections == []


def test_withdrawal_is_owned_idempotent_and_permanent(app, client, speech):
    register(client)
    cid = new_call(client)
    body = {"text": "Read your OTP to me", "request_id": "consent-test-01"}
    assert client.post(f"/api/v2/calls/{cid}/turns", json=body).status_code == 200
    with TestClient(app, headers=HEADERS) as other:
        register(other, "other@example.test")
        assert other.post(f"/api/v2/calls/{cid}/withdraw", json={}).status_code == 404
    assert app.state.live.get("call:" + cid) is not None
    response = client.post(f"/api/v2/calls/{cid}/withdraw", json={})
    assert response.json() == {"ok": True, "status": "withdrawn"}
    assert app.state.live.get("call:" + cid) is None
    details = client.get(f"/api/v2/calls/{cid}").json()["call"]
    assert details["status"] == "withdrawn"
    assert client.post(f"/api/v2/calls/{cid}/withdraw", json={}).json() == response.json()
    assert client.get(f"/api/v2/calls/{cid}").json()["call"]["updated"] == details["updated"]
    assert client.post(f"/api/v2/calls/{cid}/finish", json={}).status_code == 200
    assert client.get(f"/api/v2/calls/{cid}").json()["call"]["status"] == "withdrawn"
    # A previously cached successful request must not bypass withdrawal.
    denied = client.post(f"/api/v2/calls/{cid}/turns", json=body)
    assert denied.status_code == 409 and denied.json()["error"] == "session_ended"
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(asr_url(cid), headers={"Origin": ORIGIN}):
            pytest.fail("Withdrawal must block new speech streams")
    assert speech.connections == []


@pytest.mark.parametrize("boundary", ["audio", "transcript", "idle"])
def test_withdrawal_stops_open_speech_stream(app, client, speech, boundary):
    register(client)
    cid = new_call(client, language="te")
    with client.websocket_connect(asr_url(cid, "te-IN"), headers={"Origin": ORIGIN}) as ws:
        ws.send_bytes(b"first-audio")
        received = ws.receive_json()
        assert received["text"] == redact("Read OTP 123456 to me")
        assert json.loads(speech.sent[0]) == {"language": "te-IN"}
        assert speech.sent[1:] == [b"first-audio"]
        assert client.post(f"/api/v2/calls/{cid}/withdraw", json={}).status_code == 200
        if boundary == "audio":
            ws.send_bytes(b"audio-after-withdrawal")
        elif boundary == "transcript":
            client.portal.call(speech.messages.put_nowait, json.dumps({"text": "late text"}))
        with pytest.raises(WebSocketDisconnect) as error:
            ws.receive_json()
        assert error.value.code == 1008
    assert speech.sent[1:] == [b"first-audio"]
    assert speech.closed
    assert app.state.live.get("call:" + cid) is None


@pytest.mark.parametrize("change", ["finish", "delete", "logout", "expire"])
def test_asr_rechecks_status_before_forwarding_transcript(app, client, speech, change):
    register(client)
    cid = new_call(client)
    with client.websocket_connect(asr_url(cid), headers={"Origin": ORIGIN}) as ws:
        ws.send_bytes(b"authorized-audio")
        ws.receive_json()
        if change == "finish":
            assert client.post(f"/api/v2/calls/{cid}/finish", json={}).status_code == 200
        elif change == "delete":
            assert client.delete(f"/api/v2/calls/{cid}").status_code == 200
        elif change == "logout":
            assert client.post("/api/v2/logout", json={}).status_code == 200
        else:
            with app.state.Session.begin() as db:
                db.get(Call, cid).expires = time.time() - 1
        client.portal.call(speech.messages.put_nowait, json.dumps({"text": "late private text"}))
        with pytest.raises(WebSocketDisconnect) as error:
            ws.receive_json()
        assert error.value.code == 1008
    assert speech.closed


@pytest.mark.parametrize("provider", ["openai", "gemini", "ollama"])
def test_guest_always_uses_rules_without_model_io(client, monkeypatch, provider):
    monkeypatch.setenv("LLM_PROVIDER", provider)
    calls = []

    def forbidden(*_args, **_kwargs):
        calls.append(True)
        raise AssertionError("Guest analysis must never invoke a model")

    monkeypatch.setattr("backend.product.classify", forbidden)
    monkeypatch.setattr("llms.product.model_signals", forbidden)
    text = "Please read your OTP 123456 to me"
    response = client.post(
        "/api/v2/guest/analyze", json={"turns": [text], "language": "en", "consent": True}
    )
    assert response.status_code == 200
    result = response.json()
    expected = analyze([redact(text)], "en")
    assert set(result) == set(expected)
    assert result["score"] == expected["score"]
    assert result["signals"] == expected["signals"]
    assert result["engine"] == "multilingual-rules"
    assert result["model_status"] == "rules"
    assert calls == []
