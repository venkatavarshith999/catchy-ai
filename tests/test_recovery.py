"""Synthetic SQLite recovery through the application; no real user data or services."""

import sqlite3
import time

import pytest
from fastapi.testclient import TestClient

from backend.product import create_app
from scripts.sqlite_recovery import copy_database, main

HEADERS = {"Origin": "http://localhost:8000", "X-Catchy-Request": "1"}
CREDENTIALS = {
    "name": "Recovery test",
    "email": "recovery@example.test",
    "password": "synthetic-recovery-password",
}


@pytest.fixture
def source(tmp_path, monkeypatch):
    for key in (
        "SMTP_HOST",
        "SMTP_FROM",
        "ALERT_WEBHOOK_URL",
        "ERROR_WEBHOOK_URL",
        "ASR_WS_URL",
        "REDIS_URL",
    ):
        monkeypatch.setenv(key, "")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("APP_ORIGIN", HEADERS["Origin"])
    monkeypatch.setenv("LLM_PROVIDER", "rules")
    path = tmp_path / "source.db"
    app = create_app("sqlite:///" + path.as_posix(), redis_url="")
    with TestClient(app, headers=HEADERS) as client:
        assert client.post("/api/v2/auth/register", json=CREDENTIALS).status_code == 200
        assert (
            client.post("/api/v2/preferences", json={"retain_transcript": True}).status_code == 200
        )
        created = client.post(
            "/api/v2/calls", json={"mode": "typed", "language": "en", "consent": True}
        )
        assert created.status_code == 201
        cid = created.json()["id"]
        result = client.post(
            f"/api/v2/calls/{cid}/turns",
            json={
                "text": "Read your OTP to me. recovery-transcript-sentinel",
                "request_id": "recovery-request-001",
            },
        )
        assert result.status_code == 200 and result.json()["level"] == "high"
        cookie = client.cookies.get("catchy_v2")
    yield path, cid, cookie
    app.state.engine.dispose()


def test_metadata_backup_restores_through_api(source, tmp_path):
    path, cid, old_cookie = source
    backup = copy_database(path, tmp_path / "backup.db")
    assert b"recovery-transcript-sentinel" not in backup.read_bytes()
    restored = copy_database(backup, tmp_path / "restored.db", restore=True)
    app = create_app("sqlite:///" + restored.as_posix(), redis_url="")
    with TestClient(app, headers=HEADERS) as client:
        client.cookies.set("catchy_v2", old_cookie)
        assert client.get("/api/v2/me").status_code == 401
        client.cookies.clear()
        assert client.post("/api/v2/auth/login", json=CREDENTIALS).status_code == 200
        detail = client.get(f"/api/v2/calls/{cid}").json()
        assert detail["call"]["status"] == "interrupted"
        assert detail["call"]["score"] >= 60 and detail["call"]["count"] == 1
        assert detail["turns"] == [] and detail["evidence"] == []
        assert detail["call"]["retain"] is False
        assert (
            client.post(
                f"/api/v2/calls/{cid}/turns",
                json={"text": "Hello", "request_id": "after-restore-001"},
            ).status_code
            == 409
        )
        assert client.delete(f"/api/v2/calls/{cid}").status_code == 200
        assert client.get(f"/api/v2/calls/{cid}").status_code == 404
    app.state.engine.dispose()
    # Reading and sanitizing the snapshot must not erase source history.
    with sqlite3.connect(path) as connection:
        assert (
            "recovery-transcript-sentinel"
            in connection.execute(
                "SELECT transcript FROM product_calls WHERE id=?", (cid,)
            ).fetchone()[0]
        )


def test_explicit_transcript_copy_and_expired_session_pruning(source, tmp_path):
    path, cid, _ = source
    backup = copy_database(path, tmp_path / "explicit.db", include_transcripts=True)
    with sqlite3.connect(backup) as connection:
        assert (
            "recovery-transcript-sentinel"
            in connection.execute(
                "SELECT transcript FROM product_calls WHERE id=?", (cid,)
            ).fetchone()[0]
        )
        connection.execute("UPDATE product_calls SET expires=?", (time.time() - 1,))
    restored = copy_database(backup, tmp_path / "expired.db", restore=True)
    with sqlite3.connect(restored) as connection:
        assert connection.execute("SELECT count(*) FROM product_calls").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM product_logins").fetchone()[0] == 0


def test_refuses_overwrite_and_requires_acknowledgement(source, tmp_path):
    path, _, _ = source
    protected = tmp_path / "protected.db"
    protected.write_bytes(b"do not overwrite")
    with pytest.raises(FileExistsError):
        copy_database(path, protected)
    assert protected.read_bytes() == b"do not overwrite"
    with pytest.raises(FileExistsError):
        copy_database(path, path)
    output = tmp_path / "not-created.db"
    with pytest.raises(SystemExit) as error:
        main(["backup", str(path), str(output)])
    assert error.value.code == 2 and not output.exists()


def test_rejects_non_product_database(tmp_path):
    source = tmp_path / "other.db"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE unrelated (id INTEGER)")
    output = tmp_path / "not-created.db"
    with pytest.raises(ValueError, match="not a supported"):
        copy_database(source, output)
    assert not output.exists()
