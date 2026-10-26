# Verification record — 13 October 2026

## Connection recovery update — 23 October 2026

The user-reported sign-in error was reproduced as an unreachable local server: neither loopback address accepted a connection on port 8000. The previous UI collapsed connection, parsing and uncategorized API errors into the misleading message that protection had stopped, even on a sign-in form.

- Python suite: **80 passed, 1 skipped**. The skipped PostgreSQL/Redis integration requires external services. The newly added HTTP test starts its own launcher with an isolated temporary database, checks every public asset, creates a synthetic account, rejects a wrong password, signs in, analyzes an OTP request, finishes the session, verifies history and rejects an untrusted origin.
- JavaScript checks: **16 API-client success/error/timeout cases**, **78 localized mode/state combinations**, and connection recovery, invalid health payload, delayed account restoration, consent, escaping and existing lifecycle regressions passed. Tests execute real UI handlers in a DOM stub; they do not establish browser layout or device behavior.
- Ruff checks passed. The new HTTP test is included in the lint scope and the normal pytest CI run; client and UI tests run through `npm run check`.
- Final JavaScript and Prettier checks passed after the startup-race and uncertain-submission fixes. Public assets were regenerated using the documented assets-only mode and copied to the existing Android public-assets directory after confirming that its native bridge was unchanged. No APK was compiled.
- The local preview launcher passed its own page/database-health checks, but a separate process could not reach it after network permission was granted (connection timeout). A detached process also ended with its parent execution command. The owned preview instance was stopped; browser reachability and a persistent hosted server are **not verified**. Start `START-HERE.bat` directly from Windows Explorer for the local demonstration.
- The refreshed 248-file source ZIP passed CRC and inventory checks and byte-for-byte checks for the updated source/tests. Runtime databases, environment files and local server logs are excluded.

This update exercises rules-only analysis. It does not establish current cloud-model availability, real audio accuracy, native call screening, SMS-inbox access, an APK build or public hosting. The Android build and browser/device limitations in the later template update remain applicable; see `docs/TEMPLATE-UPDATE.md`.

## Completed locally

- Python product/privacy/security and legacy regression suite: **79 passed**, **1 skipped**. The skipped case requires running PostgreSQL and Redis; CI configures those services.
- JavaScript syntax checks and preserved guest-engine regressions: **10 scenarios passed**, plus **2 ASR lifecycle regressions passed** and **2 session-ordering regressions passed** (stale speech timing and late microphone-permission cleanup). Two known legacy detector limitations remain documented in its evaluation set.
- Ruff lint/format and Prettier formatting: passed for the configured source scope.
- Frontend/native asset build and Capacitor Android sync: passed. Public shell tests fetch every asset in the offline manifest and check catalog key parity across all 13 enabled languages.
- npm dependency audit: **0 known vulnerabilities** at scan time.
- Python dependency audit: **no known vulnerabilities** for all 59 distributions installed in the tested environment, including development dependencies. Installed versions were enumerated and scanned with pip-audit's pinned-input/no-resolver mode because this sandbox's virtualenv lacked its own pip command. CI uses a normal pip-installed environment and scans requirements. Optional Whisper dependencies were not installed or audited here.
- Real HTTP process startup and 12 multilingual guest-analysis requests: passed. Measured text HTTP round-trip p50 **5.83 ms**, p95 **9.21 ms** on this development host. This excludes audio, recognition, a remote network and optional LLM work.
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

## OpenAI adapter update

Eleven mocked OpenAI adapter tests and one public-health configuration test passed. Coverage includes redaction, bounded context, strict request format, quoted evidence, auth/quota failures, timeout, refusal and incomplete output, missing keys, and preservation of rule warnings. No real OpenAI key was created or used, and live provider accuracy/connectivity/billing remain unverified. The hidden-key launcher argument was checked with --help; interactive key entry requires the user terminal. Frontend build, 14 JavaScript scenarios, lint/format and real local HTTP lifecycle smoke passed.

## Gemini adapter update

Ten additional mocked Gemini cases passed, covering header-only credentials, redaction, context bounds, evidence validation, auth/quota/timeout errors, blocked/incomplete/malformed responses and invalid configuration. A live synthetic request to Gemini 3.1 Flash-Lite returned valid structured output. This is a connectivity check, not a real-world accuracy or latency evaluation. The first attempted Gemini 2.5 Flash-Lite request returned model-not-found; the configured default is now Gemini 3.1 Flash-Lite. No real API key is included in source or the release ZIP.

The actual FastAPI guest-analysis route was exercised through TestClient with the live Gemini provider: HTTP 200, model_status=connected, high risk for a synthetic credential request. An extracted-ZIP real-HTTP smoke passed with 12 guest requests and the account lifecycle. A long-running port-8000 process started, but a separate-shell connection check timed out; that test process was stopped. Use START-GEMINI.bat in a user terminal for the local website; persistent browser reachability was not verified here.

## Windows launcher update

The full Python suite passed 79 tests with one PostgreSQL/Redis integration test skipped because those services are not running locally. Six new launcher tests cover occupied ports, reservation, page/API readiness, startup exits, rules-only selection, real-process --check shutdown and invalid configuration. Ruff lint and formatting passed. The actual START-WINDOWS.bat --rules --check path passed without invoking dependency installation, selected port 8001 when the default was occupied, verified HTML and API health, and exited cleanly. This does not certify browser reachability across an isolated runner boundary.

## Redesign verification — 2026-10-14

- Python suite: 79 passed, 1 PostgreSQL/Redis integration test skipped locally. First restricted run hit local socket and temporary-directory permissions; successful rerun used approved network access and a workspace temporary directory.
- Existing JavaScript checks: 14 regression scenarios passed.
- Executed home rendering for all 13 enabled languages, three modes and idle/active states (78 combinations), checking preserved result hooks, escaped dynamic language names, selected navigation, typed-input gating and disabled sample speech during analysis. This was a Node VM check, not a real browser.
- Public assets rebuilt and Capacitor Android sync passed. Formatting checked.
- Browser screenshot/device testing remains unverified; earlier automatic approval review blocked local preview access. No APK was built, and automatic SIM-call audio/screening and SMS inbox monitoring are not implemented.
