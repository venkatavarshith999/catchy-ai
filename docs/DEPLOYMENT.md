# Deployment runbook

CI runs Python/API/security tests, JavaScript checks, synthetic evaluation, a Docker health smoke test and source packaging. Passing pushes to main publish a commit-SHA-tagged image to GHCR. The separate deployment workflow is manual and uses a GitHub production environment.

These workflows are supplied as source, not remotely executed. No external repository, registry or server has been configured.

## Repository setup

1. Push the extracted source to your own GitHub repository with main as the release branch.
2. Enable Actions and package publishing. The publishing job alone receives packages:write.
3. Create a production environment and configure required reviewers. Naming the environment in YAML alone does not enable approval rules.
4. Add environment secrets DEPLOY_HOST, DEPLOY_USER, DEPLOY_SSH_KEY and DEPLOY_KNOWN_HOSTS. Verify the host key through a trusted channel; do not disable strict SSH verification.
5. Protect main with review and passing checks. Pin reviewed actions and base images to digests before a production release; this starter uses major tags.

## Host setup

Use a Linux host with Docker and Compose v2 supporting --wait. Install this source at /opt/catchy-ai. Copy deployment/.env.example to deployment/.env and fill DOMAIN and the immutable CATCHY_IMAGE. DNS must point to the host; ports 80 and 443 must be available for Caddy HTTPS.

Configure a least-privilege deployment user. For private GHCR images, authenticate the host with a read-only registry credential outside source control. The workflow does not transmit registry credentials.

From the project root, invoke scripts/deploy.sh with the published full image name as its only argument. Use a lowercase repository name and full 40-character commit SHA from a passing CI run. The GitHub deployment workflow invokes this script for subsequent releases.

## Health checks and rollback

Compose waits for application health. Success records current-image. Failure restores the previously successful application image if available. The first deployment has no previous image. This is a single-instance replacement with possible downtime, not blue-green deployment.

Image rollback does not reverse database changes. Future migrations need backward compatibility or a separately tested recovery procedure. The supplied schema supports fresh installations. Use SQLite's online backup API before upgrades, encrypt backups and test restores in isolation.

The production Compose file exposes only Caddy, configures HTTPS origin and Secure cookies, and persists data in a named volume. The local Compose file binds port 8000 to loopback. Docker must already be running.

## Troubleshooting

- Origin rejected: use the exact APP_ORIGIN including scheme, hostname and port.
- Model fallback: check provider configuration, installed model and its five-second timeout.
- Expired context: start a new session instead of silently continuing without history.
- Microphone unavailable: use typed input or a demo.
- Database permission error: the volume must be writable by container UID 10001.
- Configure external per-client throttling and monitoring before a public pilot.
