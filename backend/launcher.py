"""Start the product ASGI server and open the browser only after it is ready."""

import os
import threading
import time
import webbrowser

import uvicorn


def main():
    port = int(os.environ.get("PORT", "8000"))
    origin = os.environ.setdefault("APP_ORIGIN", f"http://localhost:{port}")
    config = uvicorn.Config(
        "backend.product:app",
        host=os.environ.get("HOST", "127.0.0.1"),
        port=port,
        access_log=False,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(150):
        if server.started:
            break
        if not thread.is_alive():
            raise SystemExit(
                "Server could not start. Read the error above. Check the port and configuration."
            )
        time.sleep(0.1)
    if not server.started:
        raise SystemExit(
            "Server did not become ready. Check PostgreSQL/Redis settings, or use the local defaults."
        )
    print(f"Catchy AI ready: {origin}", flush=True)
    print("Keep this window open. Press Ctrl+C to stop.", flush=True)
    webbrowser.open(origin)
    try:
        while thread.is_alive():
            thread.join(1)
    except KeyboardInterrupt:
        server.should_exit = True
        thread.join(10)


if __name__ == "__main__":
    main()
