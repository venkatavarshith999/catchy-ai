"""Local launcher with an owned socket, HTTP readiness and deterministic cleanup."""

import argparse
import getpass
import os
import socket
import threading
import time
import webbrowser

import httpx
import uvicorn


def bind_listener(host, port, allow_fallback=False):
    """Keep the chosen port reserved until uvicorn takes ownership of this socket."""
    ports = range(port, min(port + 11, 65536)) if allow_fallback else [port]
    last_error = None
    for candidate in ports:
        listener = socket.socket(socket.AF_INET6 if ":" in host else socket.AF_INET)
        try:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            listener.bind((host, candidate))
            listener.listen(128)
            listener.setblocking(False)
            return listener
        except OSError as error:
            last_error = error
            listener.close()
    raise OSError(
        f"Cannot listen on {host}:{port}. Close the app using this port or set PORT to another port."
    ) from last_error


def wait_ready(server, worker, address, timeout=20):
    deadline = time.monotonic() + timeout
    with httpx.Client(trust_env=False, timeout=1) as client:
        while time.monotonic() < deadline:
            if not worker.is_alive():
                raise RuntimeError("Server exited during startup. Read the error above.")
            if server.started:
                try:
                    health = client.get(address + "/api/health")
                    page = client.get(address + "/")
                    if (
                        health.status_code == 200
                        and health.json().get("status") == "ok"
                        and page.status_code == 200
                        and "text/html" in page.headers.get("content-type", "")
                    ):
                        return
                except (httpx.HTTPError, ValueError, AttributeError):
                    pass
            time.sleep(0.1)
    raise RuntimeError(
        "Local HTTP checks timed out. Check database/Redis settings and run the launcher directly in Windows, outside an isolated runner."
    )


def configure_provider(args):
    provider = (
        "openai" if args.openai else "gemini" if args.gemini else "rules" if args.rules else None
    )
    if provider == "rules":
        os.environ["LLM_PROVIDER"] = "rules"
    elif provider:
        label = "OpenAI" if provider == "openai" else "Gemini"
        key_name = "OPENAI_API_KEY" if provider == "openai" else "GEMINI_API_KEY"
        if not os.environ.get(key_name, "").strip():
            os.environ[key_name] = getpass.getpass(
                f"{label} API key (hidden; press Enter when done): "
            ).strip()
        if not os.environ.get(key_name):
            raise ValueError(
                "No key entered. Choose rules-only mode in START-HERE.bat to run without a key."
            )
        os.environ["LLM_PROVIDER"] = provider
        print(
            f"{label} configured. The first analysis checks provider connectivity; usage may incur charges.",
            flush=True,
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Start Catchy AI from your own computer")
    providers = parser.add_mutually_exclusive_group()
    providers.add_argument(
        "--openai", action="store_true", help="Prompt privately for an OpenAI key"
    )
    providers.add_argument(
        "--gemini", action="store_true", help="Prompt privately for a Gemini key"
    )
    providers.add_argument(
        "--rules", action="store_true", help="Run without an external model or key"
    )
    parser.add_argument(
        "--no-browser", action="store_true", help="Print the address without opening a browser"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check startup and HTTP health, then stop without opening a browser",
    )
    args = parser.parse_args(argv)
    server = worker = listener = None
    try:
        configure_provider(args)
        port = int(os.environ.get("PORT", "8000"))
        if not 0 <= port <= 65535:
            raise ValueError("PORT must be between 0 and 65535 (0 chooses an available port).")
        host = os.environ.get("HOST", "127.0.0.1")
        # Respect explicit ports/origins, especially deployments behind a proxy.
        fallback = "PORT" not in os.environ and "APP_ORIGIN" not in os.environ
        listener = bind_listener(host, port, fallback)
        actual_port = listener.getsockname()[1]
        probe_host = "127.0.0.1" if host == "0.0.0.0" else "::1" if host == "::" else host
        probe_host = f"[{probe_host}]" if ":" in probe_host else probe_host
        address = f"http://{probe_host}:{actual_port}"
        origin = os.environ.setdefault("APP_ORIGIN", address).rstrip("/")
        if actual_port != port:
            print(f"Using available port {actual_port}.", flush=True)
        server = uvicorn.Server(
            uvicorn.Config(
                "backend.product:app",
                host=host,
                port=actual_port,
                access_log=False,
                log_level="warning",
            )
        )
        worker = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        worker.start()
        wait_ready(server, worker, address)
        print(f"Catchy AI local HTTP checks passed: {origin}", flush=True)
        print(
            "Open the exact address above. Keep this window open; Ctrl+C stops the app.", flush=True
        )
        print(
            "If another browser cannot connect, launch START-HERE.bat directly in Windows. An isolated runner's localhost may not be reachable outside it.",
            flush=True,
        )
        if args.check:
            return 0
        if not args.no_browser:
            try:
                if not webbrowser.open(origin):
                    print(
                        "Browser did not open automatically. Copy the address above into your browser.",
                        flush=True,
                    )
            except webbrowser.Error:
                print(
                    "Browser launch failed. Copy the address above into your browser.", flush=True
                )
        while worker.is_alive():
            worker.join(1)
        raise RuntimeError(
            "The server stopped unexpectedly. Read the error above and restart the launcher."
        )
    except KeyboardInterrupt:
        print("\nStopping Catchy AI.", flush=True)
        return 0
    except (OSError, ValueError, RuntimeError, EOFError) as error:
        print(f"Startup failed: {error}", flush=True)
        return 1
    finally:
        if server:
            server.should_exit = True
        if worker and worker.is_alive():
            worker.join(5)
        if listener:
            listener.close()


if __name__ == "__main__":
    raise SystemExit(main())
