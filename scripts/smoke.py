"""Start a real HTTP service with an isolated DB; measure text-request round trips."""

import json
import os
import socket
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    artifacts = (ROOT / "artifacts").resolve()
    artifacts.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="catchy-smoke-", dir=artifacts) as temporary:
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        origin = f"http://127.0.0.1:{port}"
        env = {
            **os.environ,
            "APP_ENV": "development",
            "APP_ORIGIN": origin,
            "DATABASE_URL": "sqlite:///" + str(Path(temporary) / "smoke.db").replace("\\", "/"),
            "REDIS_URL": "",
            "LLM_PROVIDER": "rules",
            "ERROR_WEBHOOK_URL": "",
            "DEV_EMAIL_CODES": "0",
        }
        print(f"Starting isolated HTTP smoke server on port {port}", flush=True)
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "backend.product:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--no-access-log",
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        try:
            with httpx.Client(
                base_url=origin,
                timeout=2,
                trust_env=False,
                headers={"Origin": origin, "X-Catchy-Request": "1"},
            ) as client:
                deadline = time.monotonic() + 25
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError(
                            "Server exited: " + process.stderr.read().decode(errors="replace")
                        )
                    try:
                        if client.get("/api/health").status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    time.sleep(0.1)
                else:
                    raise RuntimeError("Server readiness timeout")
                assert client.get("/").status_code == 200
                assert client.get("/product.js").status_code == 200
                assert client.get("/backend/product.py").status_code == 404
                timings = []
                for text, language in [
                    ("Read your OTP to me", "en"),
                    ("अपना ओटीपी बताएं", "hi"),
                    ("మీ ఓటీపీ చెప్పండి", "te"),
                ] * 4:
                    start = time.perf_counter()
                    response = client.post(
                        "/api/v2/guest/analyze",
                        json={"language": language, "turns": [text], "consent": True},
                    )
                    assert response.status_code == 200 and response.json()["level"] == "high"
                    timings.append((time.perf_counter() - start) * 1000)
                report = {
                    "kind": "local-http-text-roundtrip",
                    "requests": len(timings),
                    "p50_ms": round(statistics.median(timings), 2),
                    "p95_ms": round(sorted(timings)[int(0.95 * len(timings)) - 1], 2),
                    "audio_end_to_end_ms": None,
                    "field_validated": False,
                }
                (ROOT / "evaluation/http-benchmark.json").write_text(
                    json.dumps(report, indent=2) + "\n", encoding="utf-8"
                )
                print(json.dumps(report))
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            diagnostics = process.stderr.read().decode(errors="replace")
            if process.returncode not in {0, 1, -15}:
                print(diagnostics[-2500:], file=sys.stderr)
            process.stderr.close()


if __name__ == "__main__":
    main()
