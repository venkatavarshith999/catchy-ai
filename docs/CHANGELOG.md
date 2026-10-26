# Safety increment — 25 October 2026

Session-bound speech authorization and withdrawal, rules-only guests, completion-aware and nonblocking voice warnings, context-sensitive credential detection, and synthetic SQLite recovery coverage. See MASTER-PHASE-RESULTS.md for verification and limitations.

# Release history

## 2026-10-23 — API connection and sign-in recovery

Separate network failure, bounded request timeout, invalid API responses, incorrect credentials, duplicate accounts and origin mismatch messages. Add a localized connection banner, read-only retry inside account dialogs, and idle/return-to-page health checks. Background health checks preserve uncertain form submissions. Gate session starts and account changes while the initial identity lookup is pending. Refresh the PWA shell cache and include the new API client in the offline asset manifest.

Add 16 API-client regression cases, localized connection-recovery and delayed-startup UI tests, and an isolated real-HTTP registration/login/analysis/history test to the existing CI checks. No external model request, email delivery or automatic write retry is introduced.

- `5f46346` — Audit the preserved v1 implementation and record the product upgrade plan.
- `4f73756` — Integrated v2 product beta: phone/family UI, multilingual resources, FastAPI/privacy/contact flows, optional providers, PWA/Android source, tests, deployment and packaging.
- Final release verification — Confirm archive integrity and extracted-copy HTTP startup, route the index alias to the product UI, and repair a missing pip bootstrap on Windows startup.

Git history stays in the development workspace; `.git` is intentionally excluded from the portable ZIP. The initial prototype is preserved in legacy files, while the default launcher starts the v2 service.

## 2.0.1

Password recovery with expiring email codes and login/context revocation; stale-session response guards; visible modal status; broader real-HTTP lifecycle smoke checks. Adds five API tests and two JavaScript lifecycle regressions. External email, APK, browser/device and infrastructure validation still require the configured environments.

## OpenAI integration update

Adds a server-side Responses API adapter, private key prompt in START-OPENAI.bat, provider configuration in health, Compose secret forwarding, multilingual consent disclosure and mocked provider regression tests. No real OpenAI request or key creation was performed; n8n remains unnecessary for classification.

## Gemini integration update

Adds Gemini 3.1 Flash-Lite contextual analysis, START-GEMINI.bat with hidden key entry, Compose configuration, cloud-processing consent disclosures and ten mocked provider tests. A synthetic live Google request succeeded. n8n is not needed for the direct backend integration.

## Windows launcher repair

Adds START-HERE.bat provider selection; offline runtime checks that skip unnecessary reinstallations; owned-port reservation and fallback for default settings; real HTML/API readiness checks; explicit failure and shutdown exit codes; and --check/--no-browser modes. Startup documentation distinguishes local HTTP success from browser access across isolated execution environments.

## 2026-10-14 — Mobile-first interface redesign

Rebuilt the primary interface with a navy, ivory and teal visual system; phone bottom navigation and desktop sidebar; distinct Listen, Check text and Practice modes; installed-language voice preview; trusted-circle entry; refreshed shared forms, history, settings and warnings. Updated English/Hindi/Telugu copy, fallback catalogs, PWA/Android branding and shell cache version. Cancel sample speech before starting analysis. Existing consent, privacy, LLM and account behavior remains in use.
