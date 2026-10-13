# Catchy AI · Product beta

A multilingual conversation-safety companion for older adults and their families. Catchy identifies suspicious **requests and pressure tactics**, shows an understandable warning, and helps the user reach someone they trust.

The product has a phone-first interface, a responsive family workspace, a FastAPI service, persistent accounts, consented contacts, optional speech/model providers, and release automation. It preserves the original prototype in separate legacy modules.

## Start on Windows

1. Extract the entire ZIP to a normal folder.
2. Install Python 3.11 or newer.
3. Double-click **START-WINDOWS.bat**. The first run needs internet to install dependencies.
4. Wait for `Catchy AI ready: http://localhost:8000` and the browser to open.
5. **Keep that terminal window open.** Closing it stops the website.

Do not open the HTML file directly. `localhost refused to connect` means the server is not listening; rerun the launcher and read its error output. If port 8000 is occupied, set `PORT=8001` in your terminal before starting. The launcher uses the same origin and port for the app.

On macOS/Linux: `sh start.sh`. To run without opening a browser:

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: . .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn backend.product:app --host 127.0.0.1 --port 8000 --no-access-log
```

Open `http://localhost:8000` exactly; origin protection intentionally rejects mismatched hosts. Local development uses SQLite and bounded in-memory live context. PostgreSQL and Redis are provided by `docker compose up --build`; Docker must be installed and running.

## Try it in three minutes

Choose English, Hindi or Telugu. Select **Try a safe demo → Scam simulation**, give consent, and watch the high-risk request trigger a full-screen warning. Repeat with **Genuine-call simulation**. Use **Type or paste** for your own synthetic examples. Microphone mode depends on your browser/device and speech provider.

Create an account to save metadata and manage the trusted circle. Redacted transcript retention is off by default. To test accepted invitations locally without SMTP, set `DEV_EMAIL_CODES=1` before launch; the verification UI will display development codes. This option is rejected in production. Invite a second account, copy the link, and let that person verify their email and accept it. A contact relationship is not active until accepted.

Email verification uses configured SMTP. Optional metadata alerts use the documented HTTPS webhook or SMTP. No paid account, model key, real email, or message delivery is required for typed analysis and simulations. The app explicitly reports unavailable delivery services.

## Included

| Area | Implementation |
| --- | --- |
| Phone experience | Large controls, consent, simple risk states, two-action danger screen, spoken warning fallback, haptics, wake lock, explicit failure states |
| Family workspace | Session filters, evidence timeline when retained, metadata export, deletion, trusted circle, preferences |
| Accounts | Email/password sessions, email verification, user/contact/admin roles, ownership checks, account deletion |
| Detection | Shared rules with native-script and romanized lexicons; optional bounded Ollama refinement; action-request gating and one warning per call |
| Speech | Browser recognition, Android speech bridge, optional self-hosted Whisper WebSocket worker |
| Privacy | No application raw-audio storage, redaction before model requests, opt-in transcript retention, expiring live memory, content-free event logging |
| Operations | PostgreSQL/Redis Compose, HTTPS proxy configuration, health/metrics, optional error webhook, tests, dependency scanning, source packaging and release workflows |
| Android | Capacitor project, native permissions/haptics/screen-awake/speech bridge, manual CI APK build workflow |

## Language status

English, Hindi and Telugu have complete UI catalogs and authored synthetic test sets. Tamil, Kannada, Malayalam, Marathi, Bengali, Gujarati, Punjabi, Odia, Urdu and Assamese have beta lexicons, script fonts and partially translated catalogs with explicit English fallbacks. Their current tests are lexicon-derived smoke tests. The remaining scheduled languages are listed as planned and disabled. Urdu uses RTL layout.

All enabled languages remain **beta**. Speech availability depends on installed/browser services; native-speaker and device review are still needed. The evaluation does not establish real-world accuracy. See `evaluation/multilingual-results.json` for every measured result, including misses.

## Important product boundaries

- Catchy cannot intercept or end a normal cellular call. Same-phone calls may block microphone access. Use an authorized conversation on a second device when necessary.
- Browser and native recognition may send audio to the platform's speech service. The self-hosted option processes audio in memory on your server. The app's no-storage promise does not describe external vendors' retention policies.
- Keep Catchy visible. Backgrounding, loss of connectivity, silence and recognition failures stop protection with an explanation.
- The included simulations are text playback, not a network VoIP service. Provider/OEM integration is future work.
- A low-risk result does not verify a caller. A risk score is not a probability of fraud.
- APK compilation, hardware speech tests, independent accessibility review and production deployment have not been completed in this environment. No compiled APK is included. This is a product beta source release, not a certified public service.

## Project layout

```text
frontend/       Phone and family UI, catalogs, PWA, fonts and bundled bridge
backend/        FastAPI API, SQLAlchemy models, providers, rules and observability
backend/signals/ Data-only multilingual detection lexicons
llms/           Optional contextual model integration and legacy detector
database/       Initial schema documentation and SQL
mobile/         Native bridge source (web assets generated by npm run build)
android/        Capacitor Android source and Gradle wrapper
data/<lang>/    Synthetic evaluation cases only
evaluation/    Per-language evaluation and measured reports
tests/         Product/privacy/security, service integration and legacy regressions
scripts/       Build, smoke benchmark, packaging and deployment helpers
deployment/    HTTPS production Compose configuration
docs/          Architecture, API, deployment, Android, decisions and verification
.github/        CI, release image, deployment and Android build workflows
```

## Developer commands

Python runs the website; Node 22+ is only needed to rebuild fonts/native assets and run JavaScript checks. Built frontend assets are included in the ZIP.

```sh
python -m pip install -r requirements-dev.txt
npm ci
npm run build
npm run check
npm run format:check
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
python -m evaluation.multilingual
python scripts/smoke.py
python -m pip_audit -r requirements.txt
npm audit --audit-level=moderate
python scripts/package.py
```

`TEST_DATABASE_URL` and `TEST_REDIS_URL` enable the integration test; CI supplies both. The smoke script starts its own temporary server/database and measures local HTTP text-analysis latency. It does not measure audio end-to-end latency. Real speech-end-to-result timings appear in the UI only when the provider supplies a timestamp.

Environment variables are documented in `.env.example`. Python does not automatically load that file; export variables in your shell. Docker Compose reads `.env`. Use `docs/DEPLOYMENT.md` and `docs/ANDROID.md` for deployment and APK builds. See `docs/VERIFICATION.md` for what was actually run.
