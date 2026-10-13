# Verification record — 13 October 2026

## Completed locally

- Python product/privacy/security and legacy regression suite: **51 passed**, **1 skipped**. The skipped case requires running PostgreSQL and Redis; CI configures those services.
- JavaScript syntax checks and preserved guest-engine regressions: **10 scenarios passed**, plus **2 ASR lifecycle regressions passed** and **2 session-ordering regressions passed** (stale speech timing and late microphone-permission cleanup). Two known legacy detector limitations remain documented in its evaluation set.
- Ruff lint/format and Prettier formatting: passed for the configured source scope.
- Frontend/native asset build and Capacitor Android sync: passed. Public shell tests fetch every asset in the offline manifest and check catalog key parity across all 13 enabled languages.
- npm dependency audit: **0 known vulnerabilities** at scan time.
- Python dependency audit: **no known vulnerabilities** for all 59 distributions installed in the tested environment, including development dependencies. Installed versions were enumerated and scanned with pip-audit's pinned-input/no-resolver mode because this sandbox's virtualenv lacked its own pip command. CI uses a normal pip-installed environment and scans requirements. Optional Whisper dependencies were not installed or audited here.
- Real HTTP process startup and 12 multilingual guest-analysis requests: passed. Measured text HTTP round-trip p50 **3.6 ms**, p95 **5.43 ms** on this development host. This excludes audio, recognition, a remote network and optional LLM work.
- Synthetic multilingual evaluation: **260 cases**, 20 per enabled language. Authored development examples for English/Hindi/Telugu; lexicon-derived smoke fixtures for the other ten. No independent holdout.

## Measured Wave 1 text results

| Language | Precision | Recall | F1 | Text engine p95 |
| --- | --- | --- | --- | --- |
| English | 1.000 | 0.900 | 0.947 | 3.851 ms |
| Hindi | 1.000 | 1.000 | 1.000 | 7.143 ms |
| Telugu | 1.000 | 1.000 | 1.000 | 8.323 ms |

Inspect `evaluation/multilingual-results.json` for every case and later-language metric. Gujarati smoke recall is 0.800; do not hide its two missed cases. Perfect scores on ten positives/ten negatives are not evidence of field reliability. These development samples are tiny and partly constructed from the detector's lexicons.

## Not verified in this environment

- Browser visual, keyboard, screen-reader and phone layout QA: browser access was blocked by the tool's security policy. No alternative browser-control route was used.
- Microphone capture, browser/native speech, TTS voices, Bluetooth, call/microphone contention, offline installation and real audio end-to-end latency. The under-three-second audio target is unmeasured.
- Self-hosted Whisper/Ollama runtime and native-speaker review. Later beta catalogs are partial translations.
- Docker runtime and the actual PostgreSQL/Redis integration test: no running Docker daemon/services available locally.
- Android Gradle compilation, APK installation, release signing and app-store submission: Android SDK unavailable. Source and manual build workflow are included.
- Real SMTP/SMS/WhatsApp delivery, hosting, HTTPS production rollout and remote GitHub Actions: no provider credentials or deployment target were supplied. Alert tests use mocks and verify metadata/consent behavior.

One test-client deprecation warning comes from FastAPI/Starlette's current httpx adapter. It does not fail the suite; migrate the test transport when the upstream compatibility path is finalized.

This is a tested product beta source release. These remaining checks must be completed before presenting it as a validated public safety service.

## Archive verification

The source ZIP passed CRC/inventory checks, excluded runtime databases and credentials, and included all 13 synthetic fixture sets, frontend assets, backend, SQL schema, native source and workflows. An extracted copy started its own real HTTP server and passed the 12-request multilingual smoke check using the installed Python dependencies (p50 9.96 ms, p95 20.11 ms). This also excludes audio recognition. The final documentation and startup-alias correction were packaged after that check.

## 2.0.1 continuation

Added password recovery, five API regressions (revocation/context cleanup, absent-account response shape, attempt/expiry limits, deleted/recreated accounts, request/input limits), session-generation guards and status messages inside dialogs. Unit tests mock or disable delivery; no real email or external notification was sent. The HTTP smoke now also checks registration, cookie authentication, a signed-in risk update, retention off, session finish and account deletion. Browser/device and deployment limitations above remain.
