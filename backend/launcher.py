"""Start the local service before opening the website."""
import os
import threading
import webbrowser
from http.server import ThreadingHTTPServer
from backend.server import Handler, cleanup_memory
from backend.storage import initialize


def main():
    port = int(os.environ.get('PORT', '8000'))
    origin = os.environ.get('APP_ORIGIN', f'http://localhost:{port}')
    initialize()
    try:
        server = ThreadingHTTPServer((os.environ.get('HOST', '127.0.0.1'), port), Handler)
    except OSError as error:
        raise SystemExit(f'Cannot start on port {port}: {error}\nAnother server may already be running. Try opening {origin}.')
    server.daemon_threads = True
    threading.Thread(target=cleanup_memory, daemon=True).start()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f'Catchy AI is ready: {origin}', flush=True)
    print('KEEP THIS WINDOW OPEN while using the website. Press Ctrl+C to stop.', flush=True)
    print('If the browser does not open, copy the URL above.', flush=True)
    webbrowser.open(origin)
    try:
        while thread.is_alive():
            thread.join(timeout=1)
    except KeyboardInterrupt:
        print('\nStopping Catchy AI.')
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
