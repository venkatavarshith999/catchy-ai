# Windows startup and browser timeouts

Extract the whole ZIP, then double-click **START-HERE.bat in Windows Explorer**. Choose 1 for Gemini, 2 for rules-only, or 3 for OpenAI. A provider key is entered at a hidden terminal prompt, never saved to a file. For a basic website test, choose 2; Gemini can be selected on the next launch.

The launcher checks installed package versions and imports before using pip. A matching runtime needs no installation network access. Missing, changed or broken dependencies trigger setup. Python 3.11 or newer is required. The optional Whisper service is a separate installation.

The launcher reserves its listening socket, starts the server, and checks both `/api/health` and the home page through local HTTP. It only opens the browser after both pass. It prints the exact URL and keeps the terminal running. Closing the window or pressing Ctrl+C stops the website.

## If the browser times out

A server running inside an isolated automation environment may answer requests inside that environment while remaining unreachable from Windows browsers. That behavior was observed during this build. Changing ports inside the same isolated environment did not establish browser access. Launch the batch file directly in Windows instead. No firewall changes, tunneling or security-policy changes are made by this release.

Use the exact printed address. The local launcher defaults to IPv4 loopback (`127.0.0.1`); manually running uvicorn without APP_ORIGIN still uses the application's `http://localhost:8000` default. These are different browser origins, so do not substitute one for the other after the page opens.

If port 8000 is occupied and neither PORT nor APP_ORIGIN was explicitly supplied, the launcher tries through port 8010. It does not stop the process using the old port. If a port/origin was explicitly configured, it reports a failure instead of silently changing that configuration. A free port fixes a port conflict; it cannot remove execution-environment isolation.

If you still see a timeout after starting directly in Windows, keep the terminal open and share its last error lines and printed URL. Do not include API keys. The internal health check does not verify a separately configured proxy, browser connection, Gemini billing or provider availability.

## If the page opens but sign-in says it cannot connect

The installed/cached web app can still display its interface after the local server has stopped. It cannot sign in, save sessions or analyze text without that server. Start **START-HERE.bat**, keep the window open, and use its exact printed address. On an already open page, select **Retry connection** after restarting. If the old error wording remains, reload the page once while the server is running to fetch the updated interface.

The app now checks the API at startup, on reconnect, when returning to the page, and every 30 seconds while idle. It shows a connection banner and a retry action inside failed account forms. Wrong passwords, existing accounts, origin mismatches and network failures have different messages. A health check does not automatically repeat a submitted form or restart microphone listening. If a submission timed out, check whether it completed before submitting again.

Local startup is for development and demonstrations. For access without keeping this computer's server running, deploy the included backend and database using the hosting instructions in `docs/DEPLOYMENT.md`; opening or installing the frontend alone does not host the backend.

## Checks without a browser

From the extracted project folder, run:

```bat
START-WINDOWS.bat --rules --check
```

This performs setup if needed, verifies HTTP startup, stops the server and reports failure using a nonzero exit code. The batch file pauses so errors remain visible. With an existing runtime you can also use:

```bat
.venv\Scripts\python.exe -m backend.launcher --rules --check
.venv\Scripts\python.exe -m backend.launcher --rules --no-browser
```

The first command exits after verification; the second keeps the server running. API keys are not needed for either check.
