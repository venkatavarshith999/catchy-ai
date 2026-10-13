# Product decisions

- Preserve the v1 family dashboard and rule evidence structure; add modular phone UI and a versioned product backend rather than discard the existing project.
- New product API uses FastAPI/SQLAlchemy. SQLite is the one-command development fallback; Compose provisions PostgreSQL and Redis. Local fallback is explicitly labeled.
- Speakerphone capture is foreground, device-dependent. Same-device cellular microphone contention is a known limitation. Use a second device or authorized test audio when capture is unavailable.
- English, Hindi and Telugu ship as beta until native-speaker and device validation. Ten later packs are partial-translation beta with lexicon-derived smoke fixtures; the remaining ten scheduled languages are planned/disabled, never silently treated as validated.
- Datasets are authored synthetic development cases. Metrics do not establish field accuracy or end-to-end audio latency.
- Contact invitations require the invited signed-in email account to accept. Invitation links are copied/shared by the user; the app never automatically sends invitations. Verification and optional metadata alerts use SMTP when configured. Alerts are never represented as sent when no provider is configured.
- SMS/WhatsApp is an optional operator webhook with a strict metadata payload. No credentials are bundled and no messages are sent during development.
- Android audio capture stops on backgrounding; no claim of background cellular protection. PWA works over HTTPS or localhost.
- Privacy and Terms pages are product drafts that require operator details and legal review before public release.

- Guest v2 analysis uses the backend temporarily for shared multilingual behavior; only the preserved legacy guest engine is local/offline. The product clearly says live protection is unavailable offline.
- No live VoIP service is provisioned. Current demos are text simulations; provider/OEM work remains a future integration.
- Native wrapper loads an operator-controlled HTTPS deployment, retaining same-origin cookies and sharing the web code. An unconfigured source build is not a usable offline APK.
