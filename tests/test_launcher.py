import os
import socket
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from backend.launcher import bind_listener, configure_provider, wait_ready

ROOT = Path(__file__).resolve().parents[1]


def test_occupied_port_is_not_stolen_and_fallback_socket_stays_reserved():
    occupied = bind_listener("127.0.0.1", 0)
    selected = None
    try:
        port = occupied.getsockname()[1]
        with pytest.raises(OSError, match="Cannot listen"):
            bind_listener("127.0.0.1", port)
        selected = bind_listener("127.0.0.1", port, allow_fallback=True)
        assert selected.getsockname()[1] != port
        with pytest.raises(OSError):
            bind_listener("127.0.0.1", selected.getsockname()[1])
    finally:
        occupied.close()
        if selected:
            selected.close()


def test_readiness_waits_for_both_health_and_html(monkeypatch):
    attempts = []

    class Client:
        def __init__(self, **kwargs):
            assert kwargs["trust_env"] is False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url):
            attempts.append(url)
            if url.endswith("/api/health"):
                return httpx.Response(200, json={"status": "ok"})
            # A listening API is insufficient if the page is still unavailable.
            return httpx.Response(
                503 if len(attempts) == 2 else 200,
                text="<html></html>",
                headers={"content-type": "text/html"},
            )

    monkeypatch.setattr("backend.launcher.httpx.Client", Client)
    wait_ready(
        SimpleNamespace(started=True),
        SimpleNamespace(is_alive=lambda: True),
        "http://127.0.0.1:8000",
        timeout=1,
    )
    assert len(attempts) == 4


def test_exited_server_is_reported_without_opening_browser():
    with pytest.raises(RuntimeError, match="exited"):
        wait_ready(
            SimpleNamespace(started=False),
            SimpleNamespace(is_alive=lambda: False),
            "http://127.0.0.1:8000",
            timeout=1,
        )


def test_rules_selection_does_not_prompt_for_cloud_credentials(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setattr(
        "backend.launcher.getpass.getpass", lambda *a: pytest.fail("No prompt expected")
    )
    configure_provider(SimpleNamespace(gemini=False, openai=False, rules=True))
    assert os.environ["LLM_PROVIDER"] == "rules"


def test_real_launcher_check_exits_and_releases_socket(tmp_path):
    env = {
        **os.environ,
        "PORT": "0",
        "HOST": "127.0.0.1",
        "APP_ENV": "development",
        "DATABASE_URL": "sqlite:///" + str(tmp_path / "launcher.db"),
        "REDIS_URL": "",
        "ERROR_WEBHOOK_URL": "",
        "DEV_EMAIL_CODES": "0",
    }
    env.pop("APP_ORIGIN", None)
    env.pop("GEMINI_API_KEY", None)
    env.pop("OPENAI_API_KEY", None)
    result = subprocess.run(
        [sys.executable, "-m", "backend.launcher", "--rules", "--check"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=35,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    line = next(line for line in result.stdout.splitlines() if "local HTTP checks passed:" in line)
    port = int(line.rsplit(":", 1)[1])
    with socket.socket() as probe:
        probe.settimeout(1)
        assert probe.connect_ex(("127.0.0.1", port)) != 0


def test_invalid_port_prints_actionable_error_without_traceback():
    env = {**os.environ, "PORT": "invalid", "LLM_PROVIDER": "rules"}
    result = subprocess.run(
        [sys.executable, "-m", "backend.launcher", "--rules", "--check"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 1
    assert "Startup failed:" in result.stdout and "Traceback" not in result.stderr
