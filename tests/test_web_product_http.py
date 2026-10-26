"""Exercise the shipped HTTP launcher and UI/API contract using synthetic data only."""

import os
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _wait_for_origin(process, timeout=30):
    """Read only the launcher's known readiness line, without exposing process output."""
    addresses = queue.Queue()

    def read_output():
        for line in process.stdout:
            match = re.fullmatch(
                r"Catchy AI local HTTP checks passed: (http://127\.0\.0\.1:\d+)\s*", line
            )
            if match:
                addresses.put(match.group(1))
        addresses.put(None)

    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            origin = addresses.get(timeout=max(0.001, min(0.25, deadline - time.monotonic())))
        except queue.Empty:
            continue
        if origin:
            return origin, reader
        pytest.fail("The isolated HTTP launcher exited before reporting readiness.")
    pytest.fail("The isolated HTTP launcher did not become ready within 30 seconds.")


def test_shipped_web_auth_and_typed_session_over_http(tmp_path):
    # Inherit only runtime essentials. No real DB, provider keys, delivery endpoints,
    # proxy settings, or deployment configuration enter this subprocess.
    runtime_keys = {
        "PATH",
        "SYSTEMROOT",
        "WINDIR",
        "COMSPEC",
        "PATHEXT",
        "TEMP",
        "TMP",
        "PYTHONPATH",
    }
    env = {key: value for key, value in os.environ.items() if key.upper() in runtime_keys}
    env.update(
        {
            "APP_ENV": "development",
            "HOST": "127.0.0.1",
            "PORT": "0",
            "DATABASE_URL": "sqlite:///" + (tmp_path / "web-http.db").as_posix(),
            "REDIS_URL": "",
            "LLM_PROVIDER": "rules",
            "DEV_EMAIL_CODES": "0",
            "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    process = subprocess.Popen(
        [sys.executable, "-m", "backend.launcher", "--rules", "--no-browser"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    reader = None
    try:
        origin, reader = _wait_for_origin(process)
        with httpx.Client(
            base_url=origin,
            headers={"Origin": origin, "X-Catchy-Request": "1"},
            timeout=5,
            trust_env=False,
        ) as client:
            page = client.get("/")
            assert page.status_code == 200
            assert "text/html" in page.headers.get("content-type", "")
            for reference in ("/product.js", "/product.css", "/assets/template-water.webp"):
                assert reference in page.text

            health = client.get("/api/health")
            assert health.status_code == 200
            assert health.json()["status"] == "ok"
            assert health.json()["llm"]["provider"] == "rules"

            manifest = client.get("/shell-assets.json")
            assert manifest.status_code == 200
            paths = manifest.json()
            assert isinstance(paths, list)
            required = {
                "/product.js",
                "/product.css",
                "/assets/template-water.webp",
                "/fonts/template/Inter.ttf",
                "/fonts/template/Fraunces.ttf",
            }
            if (ROOT / "frontend" / "api-client.js").is_file():
                required.add("/api-client.js")
            assert required.issubset(paths)
            for path in paths:
                # Keep this test on the isolated local server even if the manifest changes.
                assert isinstance(path, str) and path.startswith("/")
                assert not path.startswith("//") and not path.startswith("/api/")
                asset = client.get(path)
                assert asset.status_code == 200, f"Missing public shell asset: {path}"
                assert asset.content, f"Empty public shell asset: {path}"

            credentials = {
                "email": "http-smoke@example.test",
                "password": "synthetic-http-password-123",
            }
            registered = client.post(
                "/api/v2/auth/register", json={**credentials, "name": "HTTP Test"}
            )
            assert registered.status_code == 200
            assert registered.json()["user"]["email"] == credentials["email"]
            assert client.cookies.get("catchy_v2")
            assert client.post("/api/v2/logout", json={}).status_code == 200
            assert client.get("/api/v2/me").status_code == 401

            incorrect = client.post(
                "/api/v2/auth/login",
                json={**credentials, "password": "synthetic-wrong-password"},
            )
            assert incorrect.status_code == 401
            assert incorrect.json() == {"error": "invalid_credentials"}
            assert client.cookies.get("catchy_v2") is None

            signed_in = client.post("/api/v2/auth/login", json=credentials)
            assert signed_in.status_code == 200
            current = client.get("/api/v2/me")
            assert current.status_code == 200
            assert current.json()["user"]["email"] == credentials["email"]

            created = client.post(
                "/api/v2/calls",
                json={
                    "title": "Synthetic HTTP session",
                    "language": "en",
                    "mode": "typed",
                    "consent": True,
                },
            )
            assert created.status_code == 201
            call_id = created.json()["id"]
            analyzed = client.post(
                f"/api/v2/calls/{call_id}/turns",
                json={"text": "Read your OTP to me", "request_id": "http-smoke-turn-001"},
            )
            assert analyzed.status_code == 200
            assert analyzed.json()["level"] == "high"
            assert analyzed.json()["signals"]
            assert client.post(f"/api/v2/calls/{call_id}/finish", json={}).status_code == 200
            history = client.get("/api/v2/calls")
            assert history.status_code == 200
            saved = next(item for item in history.json()["calls"] if item["id"] == call_id)
            assert saved["status"] == "completed" and saved["count"] == 1

            rejected = client.post(
                "/api/v2/auth/login",
                headers={"Origin": "https://untrusted.example.test"},
                json=credentials,
            )
            assert rejected.status_code == 403
            assert rejected.json() == {"error": "origin_rejected"}
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        if reader:
            reader.join(timeout=1)
        process.stdout.close()
