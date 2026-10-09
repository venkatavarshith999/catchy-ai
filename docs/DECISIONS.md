# Product decisions

- Preserve the v1 family dashboard and rule evidence structure; add modular phone UI and a versioned product backend rather than discard the existing project.
- New product API uses FastAPI/SQLAlchemy. SQLite is the one-command development fallback; Compose provisions PostgreSQL and Redis. Local fallback is explicitly labeled.
- Speakerphone capture is foreground, device-dependent. Same-device cellular microphone contention is a known limitation. Use a second device or authorized test audio when capture is unavailable.
- English, Hindi and Telugu ship as beta until native-speaker and device validation. Other scheduled languages are listed as preview/planned, never silently treated as validated.
- Datasets are authored synthetic development cases. Metrics do not establish field accuracy or end-to-end audio latency.
- Contact invitations require the invited signed-in email account to accept. Invitation delivery and alert delivery use SMTP when configured; development UI provides a copyable invitation link. Alerts are never represented as sent when no provider is configured.
- SMS/WhatsApp is an optional operator webhook with a strict metadata payload. No credentials are bundled and no messages are sent during development.
- Android audio capture stops on backgrounding; no claim of background cellular protection. PWA works over HTTPS or localhost.
- Privacy and Terms pages are product drafts that require operator details and legal review before public release.
