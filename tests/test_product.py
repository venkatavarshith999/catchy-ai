import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.detection import analyze, detect_language, redact
from backend.product import create_app
from backend.product_store import Call, Login, User

ORIGIN = "http://localhost:8000"
HEADERS = {"Origin": ORIGIN, "X-Catchy-Request": "1"}


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ORIGIN", ORIGIN)
    monkeypatch.setenv("DEV_EMAIL_CODES", "1")
    for name in ["SMTP_HOST", "SMTP_FROM", "ALERT_WEBHOOK_URL", "ERROR_WEBHOOK_URL"]:
        monkeypatch.setenv(name, "")
    monkeypatch.setenv("LLM_PROVIDER", "rules")
    monkeypatch.delenv("REDIS_URL", raising=False)
    return create_app("sqlite:///" + str(tmp_path / "product.db"), redis_url="")


@pytest.fixture
def client(app):
    with TestClient(app, headers=HEADERS) as c:
        yield c


def register(client, email="one@example.test"):
    r = client.post(
        "/api/v2/auth/register",
        json={"name": "Example", "email": email, "password": "sample-password-123"},
    )
    assert r.status_code == 200, r.text
    return r.json()["user"]


def verify(client):
    r = client.post("/api/v2/verify/request", json={})
    assert r.status_code == 200, r.text
    assert (
        client.post(
            "/api/v2/verify/confirm", json={"code": r.json()["development_code"]}
        ).status_code
        == 200
    )


def new_call(client, language="en"):
    r = client.post(
        "/api/v2/calls",
        json={"title": "Test", "language": language, "mode": "typed", "consent": True},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def turn(client, cid, text, request_id="request-0001"):
    return client.post(f"/api/v2/calls/{cid}/turns", json={"text": text, "request_id": request_id})


def test_origin_and_validation_redacts_errors(client):
    assert (
        client.post(
            "/api/v2/auth/register", headers={"Origin": "https://evil.test"}, json={}
        ).status_code
        == 403
    )
    r = client.post("/api/v2/auth/register", json={"password": "secret123"})
    assert r.status_code == 422 and "secret123" not in r.text


def test_auth_logout_ownership(app, client):
    register(client)
    cid = new_call(client)
    other = TestClient(app, headers=HEADERS)
    register(other, "two@example.test")
    assert other.get("/api/v2/calls/" + cid).status_code == 404
    assert other.delete("/api/v2/calls/" + cid).status_code == 404
    assert client.post("/api/v2/logout", json={}).status_code == 200
    assert client.get("/api/v2/me").status_code == 401


def test_no_retention_idempotence_and_gating(client):
    register(client)
    cid = new_call(client)
    r = turn(client, cid, "Read your OTP to me").json()
    assert r["level"] == "high" and r["alert_new"]
    again = turn(client, cid, "Read your OTP to me").json()
    assert again == r
    later = turn(client, cid, "Send money now", "request-0002").json()
    assert not later["alert_new"]
    detail = client.get("/api/v2/calls/" + cid).json()
    assert detail["turns"] == [] and detail["evidence"] == [] and detail["call"]["count"] == 2
    client.post("/api/v2/calls/" + cid + "/finish", json={})
    assert turn(client, cid, "Hello", "request-0003").status_code == 409


def test_opt_in_redaction_deletion(app, client):
    register(client)
    assert client.post("/api/v2/preferences", json={"retain_transcript": True}).status_code == 200
    cid = new_call(client)
    assert turn(client, cid, "Please read OTP 123456 to me").status_code == 200
    assert "123456" not in client.get("/api/v2/calls/" + cid).text
    assert client.delete("/api/v2/account").status_code == 200
    with app.state.Session() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 0
        assert db.scalar(select(func.count()).select_from(Call)) == 0
        assert db.scalar(select(func.count()).select_from(Login)) == 0
    assert app.state.live.get("call:" + cid) is None


def test_ttl_fails_explicitly(app, client):
    register(client)
    cid = new_call(client)
    app.state.live.delete("call:" + cid)
    assert turn(client, cid, "Read your OTP").json()["error"] == "context_expired"


def test_websocket_auth_and_turns(client):
    register(client)
    cid = new_call(client)
    with client.websocket_connect("/api/v2/live/" + cid, headers={"Origin": ORIGIN}) as ws:
        ws.send_json({"text": "Read your OTP to me", "request_id": "ws-request-1"})
        assert ws.receive_json()["level"] == "high"
        client.post("/api/v2/logout", json={})
        ws.send_json({"text": "Hello", "request_id": "ws-request-2"})
        assert ws.receive_json()["error"] == "sign_in_required"


def test_guest_consent_and_caps(client):
    assert (
        client.post(
            "/api/v2/guest/analyze",
            json={"turns": ["Read OTP to me"], "language": "en", "consent": False},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v2/guest/analyze",
            json={"turns": ["a" * 1501], "language": "en", "consent": True},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v2/guest/analyze",
            json={"turns": ["మీ ఓటీపీ చెప్పండి"], "language": "te", "consent": True},
        ).json()["level"]
        == "high"
    )


def test_invitation_acceptance_and_alerts(app, client, monkeypatch):
    register(client)
    verify(client)
    invite = client.post(
        "/api/v2/contacts", json={"name": "Trusted", "email": "two@example.test"}
    ).json()
    token = invite["invitation_url"].split("=")[1]
    contact = invite["contact"]["id"]
    assert (
        client.post("/api/v2/contacts/" + contact + "/notify", json={"test": True}).status_code
        == 403
    )
    other = TestClient(app, headers=HEADERS)
    register(other, "two@example.test")
    assert (
        other.post(
            "/api/v2/contacts/accept",
            json={"token": token, "phone": "+91 9000000000", "alerts": True},
        ).status_code
        == 403
    )
    verify(other)
    assert (
        other.post(
            "/api/v2/contacts/accept",
            json={"token": token, "phone": "+91 9000000000", "alerts": True},
        ).status_code
        == 200
    )
    assert (
        other.post(
            "/api/v2/contacts/accept",
            json={"token": token, "phone": "+91 9000000000", "alerts": True},
        ).status_code
        == 404
    )
    client.post("/api/v2/contacts/" + contact + "/alerts", json={"enabled": True})
    client.post("/api/v2/preferences", json={"alert_opt_in": True})
    monkeypatch.setattr("backend.product.alert_available", lambda: True)
    deliveries = []
    monkeypatch.setattr("backend.product.deliver_alert", lambda c, m: deliveries.append(m) or True)
    r = client.post("/api/v2/contacts/" + contact + "/notify", json={"test": True})
    assert r.status_code == 200 and r.json()["status"] == "provider_accepted"
    assert set(deliveries[0]) == {"risk", "time", "language"}
    assert (
        client.post("/api/v2/contacts/" + contact + "/notify", json={"test": True}).status_code
        == 429
    )


def test_alert_unconfigured_never_claims_sent(app, client, monkeypatch):
    register(client)
    verify(client)
    invite = client.post(
        "/api/v2/contacts", json={"name": "Trusted", "email": "two@example.test"}
    ).json()
    contact = invite["contact"]["id"]
    other = TestClient(app, headers=HEADERS)
    register(other, "two@example.test")
    verify(other)
    other.post(
        "/api/v2/contacts/accept",
        json={
            "token": invite["invitation_url"].split("=")[1],
            "phone": "+91 9000000000",
            "alerts": True,
        },
    )
    client.post("/api/v2/contacts/" + contact + "/alerts", json={"enabled": True})
    client.post("/api/v2/preferences", json={"alert_opt_in": True})
    monkeypatch.setattr("backend.product.alert_available", lambda: False)
    assert (
        client.post("/api/v2/contacts/" + contact + "/notify", json={"test": True}).json()["error"]
        == "delivery_not_configured"
    )


def test_admin_privacy_metrics_static(client):
    register(client)
    assert client.get("/api/v2/evaluation").status_code == 403
    assert client.get("/api/metrics").status_code == 403
    assert client.get("/backend/product.py").status_code == 404
    assert client.get("/").status_code == 200
    assert "/product.js" in client.get("/index.html").text
    assert client.get("/sw.js").status_code == 200
    assert (
        client.post("/api/v2/analytics", json={"event": "alert_shown", "consent": False}).json()[
            "recorded"
        ]
        is False
    )


@pytest.mark.parametrize(
    "language,text",
    [
        ("en", "Please read your OTP to me"),
        ("hi", "अपना ओटीपी बताएं"),
        ("hi", "apna otp batao"),
        ("te", "మీ ఓటీపీ చెప్పండి"),
        ("te", "mee otp cheppandi"),
    ],
)
def test_multilingual_credential(language, text):
    assert analyze([text], language)["level"] == "high"


@pytest.mark.parametrize(
    "language,text",
    [("en", "Never share your OTP"), ("hi", "ओटीपी साझा न करें"), ("te", "మీ ఓటీపీ చెప్పకండి")],
)
def test_protective_language(language, text):
    assert analyze([text], language)["level"] == "low"


def test_high_requires_action():
    assert (
        analyze(["I am police, you face arrest immediately, keep this secret"])["level"] != "high"
    )


def test_script_detection_and_pii():
    assert detect_language("తెలుగు") == "te" and detect_language("हिन्दी") == "hi"
    for value in ["1234 5678 9012", "4111 1111 1111 1111", "९८७६५४३२१०", "౧౨౩౪౫౬"]:
        assert value not in redact("Code: " + value)


def test_locale_completeness():
    root = Path("frontend/locales")
    keys = set(json.loads((root / "en.json").read_text(encoding="utf-8")))
    for code in ["hi", "te"]:
        assert set(json.loads((root / f"{code}.json").read_text(encoding="utf-8"))) == keys


def test_all_public_shell_assets_and_catalogs(client):
    paths = client.get("/shell-assets.json").json()
    assert not any(path.startswith("/api/") for path in paths)
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, path
    locales = Path("frontend/locales")
    registry = json.loads((locales / "languages.json").read_text(encoding="utf-8"))
    keys = set(json.loads((locales / "en.json").read_text(encoding="utf-8")))
    for row in registry:
        if row["status"] != "planned":
            assert (
                set(json.loads((locales / f"{row['code']}.json").read_text(encoding="utf-8")))
                == keys
            )
    assert client.get("/api/v2/me").headers["cache-control"] == "no-store"


def test_language_path_injection_rejected(client):
    for language in ["../en", "../../x", "EN", "en/"]:
        response = client.post(
            "/api/v2/guest/analyze",
            json={"turns": ["hello"], "language": language, "consent": True},
        )
        assert response.status_code == 422


def test_production_rejects_insecure_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_ORIGIN", "http://localhost:8000")
    with pytest.raises(RuntimeError, match="Production requires"):
        create_app("sqlite:///" + str(tmp_path / "rejected.db"))


def test_verification_expiry_is_not_extended(app, client):
    from backend.product import digest

    user = register(client)
    response = client.post("/api/v2/verify/request", json={})
    code = response.json()["development_code"]
    record = app.state.live.get("verify:" + user["id"])
    expires = record["expires"]
    wrong = "000000" if code != "000000" else "111111"
    assert client.post("/api/v2/verify/confirm", json={"code": wrong}).status_code == 400
    assert app.state.live.get("verify:" + user["id"])["expires"] == expires
    record["expires"] = 1
    record["hash"] = digest(code)
    app.state.live.set("verify:" + user["id"], record, 30)
    assert client.post("/api/v2/verify/confirm", json={"code": code}).status_code == 400


def test_context_model_timeout_preserves_rules(monkeypatch):
    import httpx

    from llms.product import classify

    monkeypatch.setenv("LLM_PROVIDER", "ollama")

    def timeout(*args, **kwargs):
        raise httpx.ReadTimeout("test")

    monkeypatch.setattr("llms.product.httpx.post", timeout)
    result = classify(["Read your OTP to me"], "en")
    assert result["level"] == "high" and result["model_status"] == "unavailable"


def test_model_cannot_invent_action_without_ask(monkeypatch):
    import httpx

    from llms.product import classify

    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    text = "Your OTP is private"

    def answer(*args, **kwargs):
        return httpx.Response(
            200,
            request=httpx.Request("POST", "http://model.test"),
            json={
                "message": {
                    "content": json.dumps(
                        {"signals": [{"key": "credential", "turn": 1, "quote": text}]}
                    )
                }
            },
        )

    monkeypatch.setattr("llms.product.httpx.post", answer)
    assert classify([text], "en")["level"] == "low"


def test_revoked_alert_permission_blocks_delivery(app, client, monkeypatch):
    register(client)
    verify(client)
    invite = client.post(
        "/api/v2/contacts", json={"name": "Trusted", "email": "two@example.test"}
    ).json()
    cid = invite["contact"]["id"]
    other = TestClient(app, headers=HEADERS)
    register(other, "two@example.test")
    verify(other)
    other.post(
        "/api/v2/contacts/accept",
        json={
            "token": invite["invitation_url"].split("=")[1],
            "phone": "+91 9000000000",
            "alerts": True,
        },
    )
    client.post("/api/v2/contacts/" + cid + "/alerts", json={"enabled": True})
    client.post("/api/v2/preferences", json={"alert_opt_in": True})
    other.post("/api/v2/contacts/" + cid + "/alerts", json={"enabled": False})
    deliveries = []
    monkeypatch.setattr("backend.product.alert_available", lambda: True)
    monkeypatch.setattr("backend.product.deliver_alert", lambda *args: deliveries.append(args))
    assert (
        client.post("/api/v2/contacts/" + cid + "/notify", json={"test": True}).status_code == 403
    )
    assert not deliveries


def test_release_package_excludes_runtime_and_secrets():
    from scripts.package import included

    for name in [
        "data/product.db",
        "data/en/real-calls.json",
        "deployment/.env",
        ".git/config",
        "mobile/web/index.html",
        "android/local.properties",
        "android/app/release.jks",
        ".venv/python.exe",
    ]:
        assert not included(Path(name)), name
    for name in [
        "data/te/cases.json",
        "frontend/phone.html",
        ".env.example",
        "android/gradle/wrapper/gradle-wrapper.jar",
    ]:
        assert included(Path(name)), name


def reset_request(client, email="one@example.test"):
    response = client.post("/api/v2/password/request", json={"email": email})
    assert response.status_code == 200, response.text
    return response.json()


def test_password_reset_revokes_sessions_and_active_context(app, client):
    register(client)
    second = TestClient(app, headers=HEADERS)
    second.post(
        "/api/v2/auth/login", json={"email": "one@example.test", "password": "sample-password-123"}
    )
    cid = new_call(client)
    code = reset_request(client)["development_code"]
    response = second.post(
        "/api/v2/password/confirm",
        json={"email": "one@example.test", "code": code, "password": "new-password-456"},
    )
    assert response.status_code == 200
    assert client.get("/api/v2/me").status_code == 401
    assert second.get("/api/v2/me").status_code == 401
    assert app.state.live.get("call:" + cid) is None
    with app.state.Session() as db:
        assert db.get(Call, cid).status == "completed"
        assert db.scalar(select(func.count()).select_from(Login)) == 0
    assert (
        client.post(
            "/api/v2/password/confirm",
            json={"email": "one@example.test", "code": code, "password": "another-password-789"},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/v2/auth/login",
            json={"email": "one@example.test", "password": "sample-password-123"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v2/auth/login", json={"email": "one@example.test", "password": "new-password-456"}
        ).status_code
        == 200
    )


def test_reset_absent_account_has_same_response_shape(client, monkeypatch):
    register(client)
    monkeypatch.setenv("DEV_EMAIL_CODES", "0")
    monkeypatch.setattr("backend.product.send_mail", lambda *args: False)
    monkeypatch.setattr("backend.product.mail_available", lambda: False)
    known = reset_request(client)
    unknown = reset_request(client, "absent@example.test")
    assert known == unknown == {"accepted": True, "email_configured": False}


def test_reset_wrong_expired_and_attempt_limited(app, client):
    from backend.product import digest

    register(client)
    code = reset_request(client)["development_code"]
    key = "reset:" + digest("one@example.test")
    expires = app.state.live.get(key)["expires"]
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        assert (
            client.post(
                "/api/v2/password/confirm",
                json={"email": "one@example.test", "code": wrong, "password": "new-password-456"},
            ).status_code
            == 400
        )
    assert app.state.live.get(key)["expires"] == expires
    assert (
        client.post(
            "/api/v2/password/confirm",
            json={"email": "one@example.test", "code": code, "password": "new-password-456"},
        ).status_code
        == 400
    )
    code = reset_request(client)["development_code"]
    record = app.state.live.get(key)
    record["expires"] = 1
    app.state.live.set(key, record)
    assert (
        client.post(
            "/api/v2/password/confirm",
            json={"email": "one@example.test", "code": code, "password": "new-password-456"},
        ).status_code
        == 400
    )


def test_reset_deletion_clears_challenge_and_cannot_reset_recreated_account(app, client):
    from backend.product import digest

    register(client)
    code = reset_request(client)["development_code"]
    assert client.delete("/api/v2/account").status_code == 200
    assert app.state.live.get("reset:" + digest("one@example.test")) is None
    register(client)
    assert (
        client.post(
            "/api/v2/password/confirm",
            json={"email": "one@example.test", "code": code, "password": "new-password-456"},
        ).status_code
        == 400
    )


def test_reset_request_rate_limit_and_invalid_input(client):
    register(client)
    for _ in range(3):
        reset_request(client)
    assert (
        client.post("/api/v2/password/request", json={"email": "one@example.test"}).status_code
        == 429
    )
    response = client.post(
        "/api/v2/password/confirm",
        json={"email": "one@example.test", "code": "123456", "password": "short"},
    )
    assert response.status_code == 422 and "short" not in response.text
