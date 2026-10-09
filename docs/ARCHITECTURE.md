# Architecture

Browser interface -> same-origin JSON API -> session authorization -> detector -> optional Ollama -> SQLite.

The browser sends complete speech-recognition segments over HTTP. This implementation does not stream raw audio or use WebSockets. It has no speaker diarization; mixed speakers can confuse attribution.

## Responsibilities

- frontend: rendering, navigation, consent, guest demos and microphone capability detection.
- backend/server.py: routing, cookie authentication, bounded validation, account ownership and lifecycle.
- backend/storage.py: SQLite connection policy and schema initialization.
- llms/engine.py: evidence extraction, redaction, policy scoring and contextual provider.
- database/001_initial.sql: constraints, owner relationships, indexes and cascading deletion.

## Decisions

The dependency-free runtime makes the ZIP easy to demonstrate. SQLite WAL and one process are intentional constraints. In-memory conversation state and rate limits are not shared across workers. Move data to PostgreSQL and memory to Redis before horizontal scaling.

Passwords use PBKDF2-HMAC-SHA256 with individual salts. Session tokens are random and stored as hashes; cookies are HttpOnly and SameSite=Strict. HTTPS deployment enables Secure. Mutations require the configured Origin and a custom request header.

Starting a session snapshots transcript retention consent. Turns are serialized with bounded locks, limited to 1,500 characters each and 60 per session. Only owner-authenticated requests can access records. The provider has a five-second timeout. The returned latency measures classification, not the full microphone-to-warning path.

## Data lifecycle

Active conversation memory is capped at 500 sessions. A sweeper runs every 30 seconds and clears sessions after 30 minutes of inactivity; ending/deleting also clears memory. Process restart loses memory. Expired context fails explicitly unless an opted-in redacted transcript can reconstruct it. Metadata persists until deleted. Backup retention is the operator's responsibility.

## Model behavior

The baseline extracts specific English pressure and request patterns. Authority and urgency alone cannot exceed the low-signal threshold. A direct credential request can trigger high risk without a complete manipulation chain. Evidence accumulates across turns.

Optional model results must use known signal keys and quote exact text from the specified turn. Output cannot invoke actions. This rejects fabricated evidence but does not establish semantic correctness. The model only adds signals, so it cannot yet reduce rule-based false positives.

The guest JavaScript detector mirrors the Python baseline. Shared fixtures reduce policy drift. Production should generate both implementations from a common policy or centralize classification.

## Next engineering phase

Use a maintained ASGI framework, managed identity and verified recovery before a public release. Add real migrations, distributed limits, privacy-preserving monitoring, authorized VoIP audio, speaker attribution, multilingual evaluation and accessibility testing with intended users. These are future capabilities, not completed features.
