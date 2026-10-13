# Catchy AI product build plan

## Repository audit

The existing v1 has vanilla HTML/CSS/JavaScript, a Python standard-library HTTP API, SQLite, an English rule engine, optional additive Ollama analysis, 17 API/engine tests, 10 guest fixtures and Docker/CI templates. It starts with python -m backend.server. The source is not yet a Git repository. Existing account/session APIs and the forest-green visual identity should be retained where practical.

Missing: phone-first PWA, multilingual UI/detection, production ASGI, PostgreSQL/Redis adapters, consented invitations/notifications, account deletion, meaningful language evaluation, self-hosted ASR integration and Android project.

## Sequence

1. Record audit, decisions and baseline; fix greeting; initialize Git and commit.
2. Add a separate accessible phone/PWA experience, service-worker app shell, honest operational/error states and full-screen alert. Preserve the family dashboard.
3. Add data-driven language catalogs, ASR/TTS interfaces and multilingual lexicons, beginning with English/Hindi/Telugu; test shared risk policy.
4. Add FastAPI product API, relational storage via SQLAlchemy with PostgreSQL configuration, Redis live state, WebSockets, verified invitations, provider-based alerts, deletion and privacy controls. Keep legacy tests as regression coverage.
5. Build per-language synthetic datasets and evaluation reports, admin evaluation APIs/page, CI checks and latency measurements.
6. Add Capacitor Android project and native capabilities with foreground-only capture, explicit permission/failure handling, build instructions and CI APK build.
7. Add later-wave language catalogs and beta support where lexicons exist; clearly identify unvalidated language/ASR support, update documentation and source ZIP.

## Acceptance and validation

Run the existing tests throughout; add tests for scoring gates, multilingual/romanized input, redaction, authentication, ownership, contact acceptance, alert deduplication, deletion, WebSocket failures, and locale completeness. Measure synthetic text classification metrics and label them accurately. Native/model/provider end-to-end validation requires the actual device/services; never substitute synthetic metrics for those results.

## Delivery

One updated source ZIP, complete setup guide and per-phase commits. No external deployment or message delivery without configured services and user action. No cellular interception or unsupported capture hacks.
