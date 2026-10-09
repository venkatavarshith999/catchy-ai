# Security and privacy notes

Implemented controls: salted password hashes; random hashed session tokens; HttpOnly/SameSite cookies; HTTPS Secure-cookie option; origin/custom-header request protection; bounded JSON input; parameterized SQL; account ownership checks; basic request throttling; static path allowlist; CSP; framing protection; no raw audio storage; opt-in transcript persistence; minimal logs; user-controlled deletion.

App code escapes text before inserting it into HTML. User text is never used as executable code or a provider URL. Model responses are constrained to evidence and cannot send messages, call contacts, or change account settings.

This is a hackathon application. Its standard-library HTTP server is not a hardened public service. Authentication is unverified email/password without recovery or MFA. SQLite files are not automatically encrypted. Cookies and transport require correctly configured HTTPS outside localhost. Text redaction is incomplete for unusual secrets and names.

Microphone recognition can send audio to browser-provider infrastructure. Consent copy discloses this before starting. No actual microphone access was exercised during automated verification. Do not imply phone-call interception or legal compliance certification.

A public release needs maintained server/auth infrastructure, security review, verified identity recovery, device/session management, distributed rate limits, backup encryption and retention policy, an abuse response process, and load testing. Configure deployment secrets only through the CI platform, never in source files.
