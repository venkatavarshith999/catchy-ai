# Deployment and operations

## Local development

`START-WINDOWS.bat` / `sh start.sh` starts the v2 service after installing Python requirements. Local defaults use SQLite and in-process context. These are not multi-worker production settings. Use exactly the configured `APP_ORIGIN` in the browser. The terminal must stay open.

`docker compose up --build` starts the same app with PostgreSQL 17 and Redis 8 on `http://localhost:8000`. The database volume persists accounts; Redis intentionally has no disk persistence, so a restart stops live sessions. No database or Redis ports are published by the deployment files. Docker was not available for a runtime check in the build environment.

## HTTPS VPS deployment

1. Use a host with Docker Compose, DNS pointed at it, and ports 80/443 available.
2. Copy the repository to `/opt/catchy-ai`. Keep its deployment files in sync with the release.
3. Copy `deployment/.env.example` to `deployment/.env`. Restrict permissions to the operator. Set DOMAIN, immutable CATCHY_IMAGE, independent strong POSTGRES_PASSWORD/REDIS_PASSWORD/METRICS_TOKEN values, and ADMIN_EMAILS as needed. Use URL-safe random database/cache passwords or percent-encode credentials in connection URLs.
4. Build/publish the image using the included passing CI pipeline, or build and push it through your own registry. Configure registry access on the host if the image is private.
5. Run `docker compose --env-file deployment/.env -f deployment/compose.production.yaml up -d --wait` from the project root.
6. Verify the HTTPS homepage, `/api/health`, account sign-in, email verification and consented test-alert flow. Review the operator-specific Privacy/Terms and add your support details before inviting real users.

Caddy terminates HTTPS and forwards WebSocket upgrades. Production app startup rejects HTTP origins, missing PostgreSQL/Redis and development verification codes. The app runs as a non-root user with a read-only filesystem; PostgreSQL/Caddy use dedicated volumes.

Configure a trusted proxy and rate-limit policy for your hosting topology. Application limits use the ASGI client address; behind Caddy without trusted forwarding, unauthenticated clients can share a proxy-wide limit. Do not enable trust for arbitrary forwarded headers. For multiple instances use the same Redis and database. Run schema changes as controlled migrations, not concurrently during rollout.

## Providers

- LLM_PROVIDER=gemini, GEMINI_API_KEY and GEMINI_MODEL enable Google Gemini contextual analysis. See `docs/GEMINI.md`. Both Compose configurations forward the server-side settings.

- SMTP_HOST, SMTP_FROM, SMTP_PORT (587 STARTTLS or 465 TLS), SMTP_USER and SMTP_PASSWORD enable verification email and optional email metadata alerts.
- ALERT_WEBHOOK_URL and ALERT_WEBHOOK_TOKEN enable an HTTPS SMS/WhatsApp adapter you operate. Its routing/incident contract is in `docs/API.md`. Creating invitations only creates copyable links; it does not send invitations automatically.
- LLM_PROVIDER=openai, OPENAI_API_KEY and OPENAI_MODEL enable OpenAI Responses API refinement. See `docs/OPENAI.md`; only the server receives the secret. LLM_TIMEOUT defaults to 5 seconds for OpenAI. Health reports configuration, not verified connectivity.
- LLM_PROVIDER=ollama, OLLAMA_URL, OLLAMA_MODEL and LLM_TIMEOUT configure contextual analysis. Provision an appropriate multilingual model separately. Rules remain active on provider failure. Do not expose Ollama directly to the internet.
- ASR_WS_URL and ASR_SERVICE_TOKEN connect the app to a private Whisper worker. Install `requirements-asr.txt`, provision model weights, and run `python -m uvicorn backend.asr_service:app --host 0.0.0.0 --port 9001 --no-access-log` on the private network. Set the same token on both processes. Never expose the worker directly without authentication and transport security. Audio chunks stay in memory; model weights are downloaded/provisioned separately. CPU capacity and speech accuracy must be tested on your hardware. The worker has not been live-tested in this release environment.
- ERROR_WEBHOOK_URL/TOKEN send only a fixed error event name, service name and timestamp. Request bodies, URLs, identity and stack traces are excluded. A failed monitoring request cannot replace the original error response.

Python reads environment variables, not `.env` files automatically. Compose substitutes `.env`; production uses the explicit `--env-file` argument. Optional provider services are not bundled or silently started.

## CI/CD

`ci.yml` runs on pushes and pull requests: Python lint/format, JavaScript checks, product and legacy tests, PostgreSQL/Redis integration, dependency audits, synthetic evaluation, HTTP smoke benchmark, container health check, and source ZIP upload. A successful main push publishes `ghcr.io/<owner>/<repo>:<commit-sha>`.

`deploy.yml` is manual. Set GitHub environment **production** with required reviewers and secrets DEPLOY_HOST, DEPLOY_USER, DEPLOY_SSH_KEY and DEPLOY_KNOWN_HOSTS. SSH host keys are verified. The host must already have the deployment checkout, Compose, registry access and environment file. Deploy a passing full commit SHA. `scripts/deploy.sh` waits for health and restores the previous application image if startup fails. It does not undo database migrations; backup/restore is separate. No workflow has been run against a remote repository from this workspace.

`android.yml` is a manual debug APK build after deployment. See `docs/ANDROID.md`.

## Data lifecycle and recovery

Back up PostgreSQL with encryption and a retention period consistent with the operator's policy. Rehearse restore into an isolated instance. Account deletion removes live SQL associations and live context; old backups need their own expiration. Anonymous aggregate counts cannot be traced to an account for individual deletion. Expired sessions/logins are periodically pruned. Invitation and alert-attempt records follow account/contact deletion; define additional long-term operational retention before wider use.

Monitor `/api/health` and authenticated `/api/metrics`. Keep HTTP access logs disabled or configure infrastructure to avoid sensitive paths, identifiers and request bodies. Error events are JSON and contain no conversation text. Test SMTP, provider timeouts, Redis loss, API downtime, browser permissions, backgrounding and native speech on target devices before public rollout.
