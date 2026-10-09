# Catchy AI
## A little clarity. A lot more peace of mind.

A complete locally runnable hackathon application: premium responsive dashboard, account-backed APIs, persistent SQLite storage, explainable scam-signal analysis and optional Ollama contextual AI.

## Start here

Extract the ZIP, open a terminal inside catchy-ai, and run:

    python -m backend.server

Open http://localhost:8000. On macOS/Linux use python3. On Windows you can double-click START-WINDOWS.bat. Python 3.11+ is required. The baseline needs no paid API key or third-party packages. Do not open index.html directly.

## Included functionality

- Six connected views: overview, live protection, session history, trusted circle, demo studio and preferences.
- Clearly labeled guest demos using a local rules engine.
- Registration, login, logout and account-private data.
- Backend analysis of typed conversations and supported browser microphone transcripts.
- Cumulative severity, transcript evidence, warnings and optional spoken guidance.
- Persistent session metadata, opt-in redacted transcripts, search, filtering, export and deletion.
- Private trusted contacts with click-to-call links. No automatic messages.
- Optional contextual AI with output validation and explicit rules fallback.
- Docker configuration, automated tests, synthetic evaluation and GitHub Actions CI/CD.

## Organization

    frontend/            Interface, styling, guest detector and browser input
    backend/             HTTP API, authentication, validation and persistence
    database/            Initial SQLite schema
    llms/                Detection rules and Ollama adapter
    tests/               API, security and detection regressions
    evaluation/          Synthetic cases and measured results
    deployment/          HTTPS proxy and production Compose configuration
    scripts/             Packaging and health-gated deployment
    docs/                Architecture, API, security, design and presentation guides
    .github/workflows/   CI and approved CD

## First run

1. Open Demo studio, select a scenario and confirm the processing notice.
2. Choose Guest workspace to create your own account. No accounts are pre-seeded.
3. Open Live protection, choose Type a conversation, start a session, and try: Please read your OTP to me.
4. End the session and inspect Session history.
5. Add a trusted contact. The Call button opens your device dialer; it does not call automatically.

Use fictional data for demonstrations. Guest history disappears on reload.

## Stack decision

This ZIP uses native HTML/CSS/JavaScript, Python standard-library HTTP services and SQLite instead of the initially proposed React/FastAPI/PostgreSQL stack. It is self-contained and starts without dependency downloads, while separating frontend, backend, data and AI modules.

It is a functional single-instance hackathon implementation, not a production-certified fraud prevention service. Before an open public launch, replace the HTTP/auth layer with a maintained production framework and managed identity, add verified recovery, load testing and independent security review.

## Optional Ollama

Install Ollama separately and download an available local model, for example with: ollama pull llama3.2

PowerShell:

    $env:LLM_PROVIDER='ollama'
    $env:OLLAMA_URL='http://127.0.0.1:11434'
    $env:OLLAMA_MODEL='llama3.2'
    python -m backend.server

macOS/Linux:

    LLM_PROVIDER=ollama OLLAMA_MODEL=llama3.2 python3 -m backend.server

Sign in to exercise server AI. Guest demos always use browser rules. The provider receives redacted text, never raw audio. The five-second provider timeout falls back to rules with an explicit status. No sub-three-second latency guarantee is made. Warm and test the selected model before presenting. The real model service was not available during verification; controlled responses tested validation and failure handling.

## Configuration

.env.example documents supported variables. Bare Python reads shell environment variables, not .env files. Docker Compose loads .env.

| Variable | Default |
|---|---|
| HOST | 127.0.0.1 |
| PORT | 8000 |
| APP_ORIGIN | http://localhost:8000 |
| COOKIE_SECURE | 0; use 1 with HTTPS |
| DATABASE_PATH | data/catchy.db |
| LLM_PROVIDER | rules; alternatively ollama |
| OLLAMA_URL | http://127.0.0.1:11434 |
| OLLAMA_MODEL | llama3.2 |

If you change the browser hostname or port, set APP_ORIGIN to that exact URL. For Docker on the host machine, the supplied compose file points Ollama to host.docker.internal.

## Verify

    python -m unittest discover -s tests -v
    node --check frontend/app.js
    node tests/test_frontend.cjs
    python -m evaluation.run

Node 20+ is needed only for JavaScript checks. Evaluation includes known weaknesses and is not an independently measured accuracy benchmark. See docs/VERIFICATION.md.

## Docker and CI/CD

    docker compose up --build

Open http://localhost:8000. A named volume persists data. Stopping containers does not remove it. GitHub workflows test, package, smoke-test containers and publish commit-tagged images after passing main-branch changes. Deployments are manually triggered through a production environment and health checked with image rollback. Nothing has been uploaded or deployed to an external account. Setup is in docs/DEPLOYMENT.md.

## Boundaries

No cellular call interception, caller identity verification, call blocking, automatic SMS, payment integrations or emergency dispatch. No email verification, password recovery or verified caregiver invitations. The baseline is English-first; microphone input requests en-IN. Other languages are unvalidated.

Severity scores are not fraud probabilities. Rules can miss new wording and misread quoted scams. AI adds evidence; it currently does not cancel rule-based false positives. Browser speech support varies and may use the browser vendor's servers. Raw audio is not stored by Catchy; text redaction is best effort.
