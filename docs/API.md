# API

Base: /api. JSON bodies. Mutations require Origin equal to APP_ORIGIN and X-Catchy-Request: 1. Bodies require Content-Type: application/json. Authentication uses the session cookie. Errors have an error string.

| Method | Route | Description |
|---|---|---|
| GET | /health | Public server/database health |
| POST | /auth/register | name, email, password (10-128 characters) |
| POST | /auth/login | email, password |
| POST | /auth/logout | Empty object; revokes all of user's sessions |
| GET | /me | Current user and configured provider |
| GET / POST | /settings | retain_transcript, spoken_warnings; strict booleans on POST |
| GET / POST | /contacts | List or create: name, phone, relationship; max five |
| DELETE | /contacts/{id} | Remove an owned contact |
| GET | /calls | Latest 100 owned sessions |
| POST | /calls | title, mode (demo/manual/microphone), consent:true |
| GET | /calls/{id} | Metadata and any retained redacted turns |
| POST | /calls/{id}/turns | text; max 1500 characters and 60 turns |
| POST | /calls/{id}/finish | Empty object; ends session and clears memory |
| DELETE | /calls/{id} | Deletes metadata and retained turns |

Analysis fields: score (0-98 severity index), level (low/caution/high), signals (key, label, weight, turn, quote), advice, engine, model_status, latency_ms and turn. Provider status is disabled, connected or unavailable. Latency is classification time, rounded to milliseconds; zero is possible.

401: unauthenticated. 403: invalid origin/header. 404: missing/unowned resource. 409: ended or expired context. 413: excessive body size. 422: invalid fields. 429: rate limit. 503: memory capacity.

Limits: 20 auth requests per ten minutes per direct peer IP; 180 API requests per minute per user. These are process-local. Behind a reverse proxy, the peer-IP auth limit is shared; public deployments need a per-client proxy limit. The app intentionally does not trust arbitrary forwarded IP headers.

No automatic retries or idempotency keys are implemented. Serialize turns and do not blindly retry a timed-out analysis request.
